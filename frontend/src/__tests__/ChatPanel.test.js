import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock sonner
jest.mock("sonner", () => ({
  toast: { error: jest.fn(), success: jest.fn(), info: jest.fn(), warning: jest.fn() },
}));

// Mock errorHandler
jest.mock("@/lib/errorHandler", () => ({
  handleError: jest.fn(),
  handleSilent: jest.fn(),
}));

// Hoisting-safe api mock
jest.mock("@/App", () => {
  const mockApi = {
    get: jest.fn(() => Promise.resolve({ data: {} })),
    post: jest.fn(() => Promise.resolve({ data: {} })),
    delete: jest.fn(() => Promise.resolve({ data: {} })),
  };
  return { api: mockApi };
});
jest.mock("@/lib/api", () => ({
  api: { get: jest.fn(), post: jest.fn() },
  API: "http://test/api",
  BACKEND_URL: "http://test",
}));

// Mock child components
jest.mock("@/components/MessageBubble", () => {
  return function MockMessageBubble({ message }) {
    return (
      <div data-testid={`message-${message.message_id}`}>
        <span>{message.content}</span>
      </div>
    );
  };
});

jest.mock("@/components/FileUpload", () => {
  const MockFileUpload = ({ onUpload }) => <div data-testid="file-upload" />;
  const FileAttachment = ({ file }) => <span data-testid="file-attachment">{file?.name}</span>;
  MockFileUpload.FileAttachment = FileAttachment;
  return { __esModule: true, default: MockFileUpload, FileAttachment };
});

jest.mock("@/components/MentionDropdown", () => {
  return function MockMentionDropdown() { return null; };
});

jest.mock("@/components/LegalComponents", () => ({
  AiDisclaimer: () => null,
}));

jest.mock("@/components/DirectiveSetup", () => {
  return function MockDirectiveSetup() { return null; };
});

jest.mock("@/components/DisagreementAuditLog", () => {
  return function MockDisagreementAuditLog() { return null; };
});

jest.mock("@/components/Skeletons", () => ({
  SkeletonChatList: () => <div data-testid="skeleton-chat-list">Loading...</div>,
}));

jest.mock("@/components/AgentActivityPanel", () => {
  return function MockAgentActivityPanel() { return null; };
});

jest.mock("@/components/NexusBrowserPanel", () => {
  return function MockNexusBrowserPanel() { return null; };
});

jest.mock("@/components/DocsPreviewPanel", () => {
  return function MockDocsPreviewPanel() { return null; };
});

import { ChatPanel } from "@/components/ChatPanel";
import { api } from "@/App";

const defaultChannel = {
  channel_id: "ch_test",
  name: "test-channel",
  ai_agents: ["claude", "chatgpt"],
  description: "A test channel",
};

const testMessages = [
  {
    message_id: "msg_1",
    content: "Hello everyone",
    sender_type: "user",
    sender_name: "Test User",
    sender_id: "user_1",
    timestamp: new Date().toISOString(),
    reactions: {},
  },
  {
    message_id: "msg_2",
    content: "Hi there! I can help.",
    sender_type: "ai",
    sender_name: "Claude",
    sender_id: "claude",
    timestamp: new Date().toISOString(),
    reactions: {},
  },
];

const defaultProps = {
  channel: defaultChannel,
  messages: testMessages,
  messagesLoading: false,
  agentStatus: {},
  isCollaborating: false,
  onSendMessage: jest.fn(),
  user: { user_id: "user_1", name: "Test User" },
  workspaceId: "ws_test",
  onToggleCodeRepo: jest.fn(),
  codeRepoOpen: false,
};

describe("ChatPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    api.get.mockResolvedValue({ data: {} });
  });

  describe("rendering", () => {
    it("renders chat panel", () => {
      render(<ChatPanel {...defaultProps} />);
      expect(screen.getByTestId("chat-panel")).toBeInTheDocument();
    });

    it("renders channel name", () => {
      render(<ChatPanel {...defaultProps} />);
      expect(screen.getByTestId("channel-name")).toHaveTextContent("test-channel");
    });

    it("renders message input area", () => {
      render(<ChatPanel {...defaultProps} />);
      expect(screen.getByTestId("message-input")).toBeInTheDocument();
    });

    it("renders send button", () => {
      render(<ChatPanel {...defaultProps} />);
      expect(screen.getByTestId("send-message-btn")).toBeInTheDocument();
    });

    it("displays messages", () => {
      render(<ChatPanel {...defaultProps} />);
      expect(screen.getByTestId("message-msg_1")).toBeInTheDocument();
      expect(screen.getByTestId("message-msg_2")).toBeInTheDocument();
    });
  });

  describe("loading state", () => {
    it("shows skeleton when messages are loading", () => {
      render(
        <ChatPanel {...defaultProps} messages={[]} messagesLoading={true} />
      );
      expect(screen.getByTestId("skeleton-chat-list")).toBeInTheDocument();
    });
  });

  describe("message sending", () => {
    it("calls onSendMessage when send button clicked with text", async () => {
      const user = userEvent.setup();
      render(<ChatPanel {...defaultProps} />);

      const input = screen.getByTestId("message-input");
      await user.type(input, "Hello world");
      await user.click(screen.getByTestId("send-message-btn"));

      expect(defaultProps.onSendMessage).toHaveBeenCalled();
    });

    it("does not send empty messages", async () => {
      const user = userEvent.setup();
      render(<ChatPanel {...defaultProps} />);
      await user.click(screen.getByTestId("send-message-btn"));
      expect(defaultProps.onSendMessage).not.toHaveBeenCalled();
    });
  });

  describe("no channel selected", () => {
    it("shows empty state when channel is null", () => {
      render(<ChatPanel {...defaultProps} channel={null} />);
      expect(screen.getByTestId("no-channel-selected")).toBeInTheDocument();
      expect(screen.getByText("Get started with your first channel")).toBeInTheDocument();
    });
  });
});
