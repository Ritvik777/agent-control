// Agent data type
export interface Agent {
  id: number;
  name: string;
  type: string;
  requests: number;
  activeControls: number;
  passRate: number;
  lastActive: string;
}

// Mock data for agents
export const agentsData: Agent[] = [
  {
    id: 1,
    name: "Customer support bot",
    type: "1st party",
    requests: 24567,
    activeControls: 37,
    passRate: 92,
    lastActive: "2 mins ago",
  },
  {
    id: 2,
    name: "Sales assistant",
    type: "1st party",
    requests: 38742,
    activeControls: 89,
    passRate: 69,
    lastActive: "4 hours ago",
  },
  {
    id: 3,
    name: "Analytics processor",
    type: "1st party",
    requests: 49123,
    activeControls: 112,
    passRate: 52,
    lastActive: "5 days ago",
  },
  {
    id: 4,
    name: "Document summarizer",
    type: "3rd party",
    requests: 31245,
    activeControls: 164,
    passRate: 98,
    lastActive: "10 mins ago",
  },
  {
    id: 5,
    name: "Glean",
    type: "3rd party",
    requests: 15678,
    activeControls: 56,
    passRate: 7,
    lastActive: "5 mins ago",
  },
  {
    id: 6,
    name: "Data extractor",
    type: "1st party",
    requests: 45389,
    activeControls: 178,
    passRate: 5,
    lastActive: "2 mins ago",
  },
  {
    id: 7,
    name: "MSFT copilot",
    type: "1st party",
    requests: 0,
    activeControls: 23,
    passRate: 88,
    lastActive: "Mar 20, 6:45 PM",
  },
];

// Helper function to get agent by ID
export const getAgentById = (id: string | number): Agent | undefined => {
  const numId = typeof id === "string" ? parseInt(id, 10) : id;
  return agentsData.find((agent) => agent.id === numId);
};
