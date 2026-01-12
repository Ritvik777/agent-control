import {
  Box,
  Button,
  Checkbox,
  Divider,
  Grid,
  Group,
  Modal,
  Select,
  Stack,
  Text,
} from "@mantine/core";
import { Switch } from "@rungalileo/jupiter-ds";
import { JsonEditor } from "json-edit-react";
import { useEffect,useState } from "react";

import type { Control } from "@/core/api/types";

interface EditControlSetProps {
  opened: boolean;
  control: Control | null;
  onClose: () => void;
  onSave: (data: any) => void;
}

export const EditControlSet = ({
  opened,
  control,
  onClose,
  onSave,
}: EditControlSetProps) => {
  const [editedControlData, setEditedControlData] = useState<any>(control);
  const [showJsonSchema, setShowJsonSchema] = useState(false);

  // Form fields state
  const [applyTo, setApplyTo] = useState<string>("LLM span");
  const [targetNode, setTargetNode] = useState<string>("All LLM nodes");
  const [evaluationInput, setEvaluationInput] = useState<boolean>(true);
  const [evaluationOutput, setEvaluationOutput] = useState<boolean>(false);
  const [action, setAction] = useState<string>("Accept");
  const [executionEnv, setExecutionEnv] = useState<string>("SDK");

  // Update edited data when control changes
  useEffect(() => {
    if (control) {
      // TODO: To be fixed when api is integrated here
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setEditedControlData(control);
    }
  }, [control]);

  const handleSave = () => {
    onSave(editedControlData);
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={control?.name}
      size='xl'
      styles={{
        body: {
          maxHeight: "75vh",
          overflow: "auto",
        },
        title: {
          fontSize: "18px",
          fontWeight: 600,
        },
        content: {
          maxWidth: "1200px",
          width: "90vw",
        },
      }}
    >
      <Grid gutter='xl'>
        {/* Left Column - Form Fields */}
        <Grid.Col span={4}>
          <Stack gap='md'>
            <Box>
              <Group gap={4} mb={4}>
                <Text size='sm' fw={500}>
                  Apply to
                </Text>
                <Text size='xs' c='dimmed'>
                  ⓘ
                </Text>
              </Group>
              <Select
                value={applyTo}
                onChange={(value) => setApplyTo(value || "LLM span")}
                data={["LLM span", "Tool span", "Agent span"]}
                size='sm'
              />
            </Box>

            <Box>
              <Group gap={4} mb={4}>
                <Text size='sm' fw={500}>
                  Target node (optional)
                </Text>
                <Text size='xs' c='dimmed'>
                  ⓘ
                </Text>
              </Group>
              <Select
                value={targetNode}
                onChange={(value) => setTargetNode(value || "All LLM nodes")}
                data={["All LLM nodes", "Specific node", "Custom"]}
                size='sm'
              />
            </Box>

            <Box>
              <Group gap={4} mb={4}>
                <Text size='sm' fw={500}>
                  Evaluation data
                </Text>
                <Text size='xs' c='dimmed'>
                  ⓘ
                </Text>
              </Group>
              <Stack gap='xs'>
                <Checkbox
                  label='Input'
                  checked={evaluationInput}
                  onChange={(e) => setEvaluationInput(e.currentTarget.checked)}
                  size='sm'
                />
                <Checkbox
                  label='Output'
                  checked={evaluationOutput}
                  onChange={(e) => setEvaluationOutput(e.currentTarget.checked)}
                  size='sm'
                />
              </Stack>
            </Box>

            <Box>
              <Group gap={4} mb={4}>
                <Text size='sm' fw={500}>
                  Action
                </Text>
                <Text size='xs' c='dimmed'>
                  ⓘ
                </Text>
              </Group>
              <Select
                value={action}
                onChange={(value) => setAction(value || "Accept")}
                data={["Accept", "Reject", "Alert"]}
                size='sm'
              />
            </Box>

            <Box>
              <Group gap={4} mb={4}>
                <Text size='sm' fw={500}>
                  Execution environment
                </Text>
                <Text size='xs' c='dimmed'>
                  ⓘ
                </Text>
              </Group>
              <Select
                value={executionEnv}
                onChange={(value) => setExecutionEnv(value || "SDK")}
                data={["SDK", "Server", "Both"]}
                size='sm'
                disabled
              />
            </Box>
          </Stack>
        </Grid.Col>

        {/* Right Column - JSON Editor */}
        <Grid.Col span={8}>
          <Stack gap='md' h='100%'>
            <Group justify='space-between' align='center'>
              <Text size='sm' fw={500}>
                Configuration parameters
              </Text>
              <Group gap='xs'>
                <Text size='xs' c='dimmed'>
                  Show JSON schema
                </Text>
                <Switch
                  checked={showJsonSchema}
                  onChange={(e) => setShowJsonSchema(e.currentTarget.checked)}
                  color='violet'
                  size='sm'
                />
              </Group>
            </Group>

            {editedControlData && (
              <Box
                style={{
                  border: "1px solid #e0e0e0",
                  borderRadius: "4px",
                  padding: "12px",
                  backgroundColor: "#fafafa",
                  minHeight: "400px",
                  maxHeight: "500px",
                  overflow: "auto",
                }}
              >
                <JsonEditor
                  data={editedControlData}
                  setData={setEditedControlData}
                  rootName='control'
                  restrictEdit={false}
                  restrictDelete={false}
                  restrictAdd={false}
                  collapse={false}
                />
              </Box>
            )}
          </Stack>
        </Grid.Col>
      </Grid>

      <Divider mt='xl' mb='md' />

      <Group justify='flex-end'>
        <Button variant='default' onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={handleSave} color='violet'>
          Save
        </Button>
      </Group>
    </Modal>
  );
};
