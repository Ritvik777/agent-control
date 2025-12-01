"""Tests for YAML watcher and hot-reload functionality."""

import asyncio
from pathlib import Path

import pytest
import yaml
from sqlalchemy import select

from agent_control_server.models import Control, ControlSet, control_set_controls
from agent_control_server.yaml_watcher import YAMLWatcher


@pytest.mark.asyncio
async def test_load_yaml_file(tmp_path: Path):
    """Test loading YAML file."""
    yaml_content = {
        "test-control": {
            "step_id": "test",
            "description": "Test control",
            "rules": [],
            "default_action": "allow"
        }
    }
    
    yaml_file = tmp_path / "test.yaml"
    with open(yaml_file, 'w') as f:
        yaml.dump(yaml_content, f)
    
    watcher = YAMLWatcher(yaml_paths=[yaml_file])
    data = await watcher.load_yaml_file(yaml_file)
    
    assert "test-control" in data
    assert data["test-control"]["step_id"] == "test"


@pytest.mark.asyncio
async def test_sync_controls_to_db_creates_new(async_db):
    """Test syncing controls creates new controls in database."""
    controls_data = {
        "new-control": {
            "step_id": "new-test",
            "description": "New control",
            "rules": [],
            "default_action": "allow"
        }
    }
    
    watcher = YAMLWatcher(yaml_paths=[], control_set_name=None)
    control_ids = await watcher.sync_controls_to_db(controls_data, async_db)
    
    assert len(control_ids) == 1
    
    # Verify control was created
    stmt = select(Control).where(Control.name == "new-control")
    result = await async_db.execute(stmt)
    control = result.scalar_one_or_none()
    
    assert control is not None
    assert control.name == "new-control"
    assert control.data["step_id"] == "new-test"


@pytest.mark.asyncio
async def test_sync_controls_to_db_updates_existing(async_db):
    """Test syncing controls updates existing controls."""
    # Create initial control
    initial_data = {
        "step_id": "test",
        "description": "Initial",
        "rules": []
    }
    control = Control(name="update-test", data=initial_data)
    async_db.add(control)
    await async_db.commit()
    
    # Update with new data
    updated_data = {
        "update-test": {
            "step_id": "test",
            "description": "Updated",
            "rules": [{"match": {"string": ["test"]}, "action": "deny", "data": "input"}]
        }
    }
    
    watcher = YAMLWatcher(yaml_paths=[], control_set_name=None)
    control_ids = await watcher.sync_controls_to_db(updated_data, async_db)
    
    assert len(control_ids) == 1
    
    # Verify control was updated
    await async_db.refresh(control)
    assert control.data["description"] == "Updated"
    assert len(control.data["rules"]) == 1


@pytest.mark.asyncio
async def test_ensure_control_set_creates_new(async_db):
    """Test ensure_control_set creates new control set."""
    # Create a control first
    control = Control(name="test-control", data={})
    async_db.add(control)
    await async_db.commit()
    await async_db.refresh(control)
    
    watcher = YAMLWatcher(
        yaml_paths=[],
        control_set_name="test-set",
        auto_create_control_set=True
    )
    
    control_set_id = await watcher.ensure_control_set([control.id], async_db)
    
    assert control_set_id is not None
    
    # Verify control set was created
    stmt = select(ControlSet).where(ControlSet.name == "test-set")
    result = await async_db.execute(stmt)
    control_set = result.scalar_one_or_none()
    
    assert control_set is not None
    assert control_set.name == "test-set"


@pytest.mark.asyncio
async def test_ensure_control_set_adds_controls_to_existing(async_db):
    """Test ensure_control_set adds controls to existing set."""
    # Create control set
    control_set = ControlSet(name="existing-set")
    async_db.add(control_set)
    await async_db.commit()
    
    # Create controls
    control1 = Control(name="control-1", data={})
    control2 = Control(name="control-2", data={})
    async_db.add_all([control1, control2])
    await async_db.commit()
    await async_db.refresh(control1)
    await async_db.refresh(control2)
    
    watcher = YAMLWatcher(
        yaml_paths=[],
        control_set_name="existing-set",
        auto_create_control_set=True
    )
    
    await watcher.ensure_control_set([control1.id, control2.id], async_db)

    # Verify controls were added to set
    stmt = select(control_set_controls.c.control_id).where(
        control_set_controls.c.control_set_id == control_set.id
    )
    result = await async_db.execute(stmt)
    control_ids = {row[0] for row in result.fetchall()}

    assert control1.id in control_ids
    assert control2.id in control_ids


@pytest.mark.asyncio
async def test_process_yaml_files(async_db, tmp_path: Path):
    """Test processing YAML files end-to-end."""
    yaml_content = {
        "control-1": {
            "step_id": "test-1",
            "description": "Control 1",
            "rules": [],
            "default_action": "allow"
        },
        "control-2": {
            "step_id": "test-2",
            "description": "Control 2",
            "rules": [],
            "default_action": "allow"
        }
    }
    
    yaml_file = tmp_path / "controls.yaml"
    with open(yaml_file, 'w') as f:
        yaml.dump(yaml_content, f)
    
    watcher = YAMLWatcher(
        yaml_paths=[yaml_file],
        control_set_name="processed-set",
        auto_create_control_set=True
    )
    
    await watcher.process_yaml_files()
    
    # Verify controls were created
    stmt = select(Control).where(Control.name.in_(["control-1", "control-2"]))
    result = await async_db.execute(stmt)
    controls = result.scalars().all()
    
    assert len(controls) == 2
    
    # Verify control set was created
    stmt = select(ControlSet).where(ControlSet.name == "processed-set")
    result = await async_db.execute(stmt)
    control_set = result.scalar_one_or_none()
    
    assert control_set is not None


@pytest.mark.asyncio
async def test_yaml_watcher_auto_discover(tmp_path: Path):
    """Test YAML watcher validates paths on init."""
    # Create valid YAML file
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text("test: {}")
    
    watcher = YAMLWatcher(
        yaml_paths=[yaml_file],
        auto_create_control_set=False
    )
    
    assert len(watcher.yaml_paths) == 1
    assert watcher.yaml_paths[0].exists()


@pytest.mark.asyncio
async def test_yaml_watcher_handles_missing_files(tmp_path: Path):
    """Test YAML watcher handles missing files gracefully."""
    missing_file = tmp_path / "nonexistent.yaml"
    
    # Should not raise error, just log warning
    watcher = YAMLWatcher(
        yaml_paths=[missing_file],
        auto_create_control_set=False
    )
    
    # Should handle gracefully
    await watcher.process_yaml_files()


@pytest.mark.asyncio
async def test_yaml_watcher_multiple_files(async_db, tmp_path: Path):
    """Test YAML watcher with multiple files."""
    yaml1_content = {
        "control-a": {
            "step_id": "test-a",
            "rules": [],
            "default_action": "allow"
        }
    }
    
    yaml2_content = {
        "control-b": {
            "step_id": "test-b",
            "rules": [],
            "default_action": "allow"
        }
    }
    
    yaml1 = tmp_path / "file1.yaml"
    yaml2 = tmp_path / "file2.yaml"
    
    with open(yaml1, 'w') as f:
        yaml.dump(yaml1_content, f)
    with open(yaml2, 'w') as f:
        yaml.dump(yaml2_content, f)
    
    watcher = YAMLWatcher(
        yaml_paths=[yaml1, yaml2],
        control_set_name="multi-file-set"
    )
    
    await watcher.process_yaml_files()
    
    # Verify both controls were created
    stmt = select(Control).where(Control.name.in_(["control-a", "control-b"]))
    result = await async_db.execute(stmt)
    controls = result.scalars().all()
    
    assert len(controls) == 2


@pytest.mark.asyncio
async def test_yaml_watcher_empty_file_handling(async_db, tmp_path: Path):
    """Test YAML watcher handles empty files."""
    empty_file = tmp_path / "empty.yaml"
    empty_file.write_text("")
    
    watcher = YAMLWatcher(yaml_paths=[empty_file])
    
    # Should handle gracefully without errors
    await watcher.process_yaml_files()


@pytest.mark.asyncio
async def test_yaml_watcher_invalid_yaml_handling(async_db, tmp_path: Path):
    """Test YAML watcher handles invalid YAML gracefully."""
    invalid_file = tmp_path / "invalid.yaml"
    invalid_file.write_text("invalid: yaml: [unclosed")
    
    watcher = YAMLWatcher(yaml_paths=[invalid_file])
    
    # Should handle gracefully without crashing
    await watcher.process_yaml_files()



