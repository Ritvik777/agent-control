"""
YAML file watcher for hot-reloading controls.

This module watches YAML files for changes and automatically updates
controls in the database when changes are detected.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from watchfiles import awatch

from .db import AsyncSessionLocal
from .models import Control, ControlSet

logger = logging.getLogger(__name__)


class YAMLWatcher:
    """Watch YAML files and auto-reload controls on changes."""

    def __init__(
        self,
        yaml_paths: list[Path] | list[str],
        control_set_name: str | None = None,
        auto_create_control_set: bool = True
    ):
        """
        Initialize the YAML watcher.

        Args:
            yaml_paths: List of YAML file paths to watch
            control_set_name: Optional control set name to group controls
            auto_create_control_set: Whether to auto-create control set
        """
        self.yaml_paths = [Path(p) for p in yaml_paths]
        self.control_set_name = control_set_name
        self.auto_create_control_set = auto_create_control_set
        self.running = False
        self._task: asyncio.Task | None = None

        # Validate paths exist
        for path in self.yaml_paths:
            if not path.exists():
                logger.warning(f"YAML file not found: {path}")

    async def load_yaml_file(self, yaml_path: Path) -> dict[str, Any]:
        """Load and parse a YAML file."""
        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f) or {}
            logger.info(f"Loaded {len(data)} control(s) from {yaml_path}")
            return data
        except Exception as e:
            logger.error(f"Failed to load {yaml_path}: {e}")
            return {}

    async def sync_controls_to_db(
        self,
        controls_data: dict[str, Any],
        db: AsyncSession
    ) -> list[int]:
        """
        Sync controls from YAML to database.

        Creates or updates controls based on name.

        Args:
            controls_data: Dictionary of control name -> control config
            db: Database session

        Returns:
            List of control IDs that were created/updated
        """
        control_ids = []

        for control_name, control_config in controls_data.items():
            try:
                # Check if control already exists
                stmt = select(Control).where(Control.name == control_name)
                result = await db.execute(stmt)
                existing_control = result.scalar_one_or_none()

                if existing_control:
                    # Update existing control
                    existing_control.data = control_config
                    logger.info(f"Updated control: {control_name} (ID: {existing_control.id})")
                    control_ids.append(existing_control.id)
                else:
                    # Create new control
                    new_control = Control(
                        name=control_name,
                        data=control_config
                    )
                    db.add(new_control)
                    await db.flush()  # Get the ID
                    logger.info(f"Created control: {control_name} (ID: {new_control.id})")
                    control_ids.append(new_control.id)

            except Exception as e:
                logger.error(f"Failed to sync control '{control_name}': {e}")
                continue

        await db.commit()
        return control_ids

    async def ensure_control_set(
        self,
        control_ids: list[int],
        db: AsyncSession
    ) -> int | None:
        """
        Ensure control set exists and contains the given controls.

        Args:
            control_ids: List of control IDs to add to set
            db: Database session

        Returns:
            Control set ID or None if not configured
        """
        if not self.control_set_name:
            return None

        try:
            # Check if control set exists
            stmt = select(ControlSet).where(ControlSet.name == self.control_set_name)
            result = await db.execute(stmt)
            control_set = result.scalar_one_or_none()

            if not control_set:
                if not self.auto_create_control_set:
                    logger.warning(f"Control set '{self.control_set_name}' not found")
                    return None

                # Create control set
                control_set = ControlSet(name=self.control_set_name)
                db.add(control_set)
                await db.flush()
                logger.info(f"Created control set: {self.control_set_name} (ID: {control_set.id})")

            # Get current controls in set by querying the association table
            from .models import control_set_controls
            current_stmt = select(control_set_controls.c.control_id).where(
                control_set_controls.c.control_set_id == control_set.id
            )
            current_result = await db.execute(current_stmt)
            current_control_ids = {row[0] for row in current_result.fetchall()}

            # Add new controls to set
            for control_id in control_ids:
                if control_id not in current_control_ids:
                    # Insert into association table
                    insert_stmt = control_set_controls.insert().values(
                        control_set_id=control_set.id,
                        control_id=control_id
                    )
                    await db.execute(insert_stmt)

                    # Get control name for logging
                    control_stmt = select(Control).where(Control.id == control_id)
                    control_result = await db.execute(control_stmt)
                    control = control_result.scalar_one_or_none()
                    if control:
                        logger.info(f"Added control {control.name} to set {self.control_set_name}")

            await db.commit()
            return control_set.id

        except Exception as e:
            logger.error(f"Failed to ensure control set: {e}")
            await db.rollback()
            return None

    async def process_yaml_files(self) -> None:
        """Process all configured YAML files."""
        all_control_ids = []

        async with AsyncSessionLocal() as db:
            for yaml_path in self.yaml_paths:
                if not yaml_path.exists():
                    continue

                # Load YAML
                controls_data = await self.load_yaml_file(yaml_path)
                if not controls_data:
                    continue

                # Sync to database
                control_ids = await self.sync_controls_to_db(controls_data, db)
                all_control_ids.extend(control_ids)

            # Update control set if configured
            if self.control_set_name and all_control_ids:
                await self.ensure_control_set(all_control_ids, db)

        logger.info(
            f"Processed {len(all_control_ids)} control(s) "
            f"from {len(self.yaml_paths)} file(s)"
        )

    async def watch(self) -> None:
        """
        Watch YAML files for changes and reload on modification.

        This is a long-running coroutine that should be run as a background task.
        """
        logger.info(f"Starting YAML watcher for {len(self.yaml_paths)} file(s)")
        logger.info(f"Watching: {[str(p) for p in self.yaml_paths]}")

        # Initial load
        try:
            await self.process_yaml_files()
            logger.info("Initial YAML load complete")
        except Exception as e:
            logger.error(f"Failed initial YAML load: {e}")

        # Watch for changes
        self.running = True
        watch_paths = [str(p.parent) for p in self.yaml_paths if p.exists()]

        if not watch_paths:
            logger.warning("No valid YAML paths to watch")
            return

        try:
            async for changes in awatch(*watch_paths):
                if not self.running:
                    break

                # Check if any of our YAML files changed
                changed_files = {Path(change[1]) for change in changes}
                our_files = set(self.yaml_paths) & changed_files

                if our_files:
                    logger.info(f"Detected changes in: {[str(f) for f in our_files]}")
                    try:
                        await self.process_yaml_files()
                        logger.info("✓ Controls reloaded from YAML")
                    except Exception as e:
                        logger.error(f"Failed to reload YAML: {e}")

        except Exception as e:
            logger.error(f"YAML watcher error: {e}")
        finally:
            self.running = False

    def start(self) -> asyncio.Task:
        """Start watching in the background."""
        if self._task and not self._task.done():
            logger.warning("YAML watcher already running")
            return self._task

        self._task = asyncio.create_task(self.watch())
        return self._task

    async def stop(self) -> None:
        """Stop the watcher."""
        logger.info("Stopping YAML watcher")
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


# Global watcher instance
_watcher: YAMLWatcher | None = None


def get_watcher() -> YAMLWatcher | None:
    """Get the global YAML watcher instance."""
    return _watcher


def configure_watcher(
    yaml_paths: list[Path] | list[str],
    control_set_name: str | None = None,
    auto_create_control_set: bool = True
) -> YAMLWatcher:
    """
    Configure the global YAML watcher.

    Args:
        yaml_paths: List of YAML file paths to watch
        control_set_name: Optional control set name
        auto_create_control_set: Whether to auto-create control set

    Returns:
        Configured YAMLWatcher instance
    """
    global _watcher
    _watcher = YAMLWatcher(
        yaml_paths=yaml_paths,
        control_set_name=control_set_name,
        auto_create_control_set=auto_create_control_set
    )
    return _watcher

