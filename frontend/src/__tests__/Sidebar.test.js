import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock sonner
jest.mock("sonner", () => ({
  toast: { error: jest.fn(), success: jest.fn(), info: jest.fn() },
  Toaster: () => null,
}));

// Mock react-router-dom
const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

// Mock errorHandler
jest.mock("@/lib/errorHandler", () => ({
  handleError: jest.fn(),
  handleSilent: jest.fn(),
}));

// Mock LanguageContext
jest.mock("@/contexts/LanguageContext", () => ({
  useLanguage: () => ({
    t: (key) => {
      const t = {
        "workspace.channelName": "Channel name",
        "common.settings": "Settings",
        "common.billing": "Billing",
      };
      return t[key] || key;
    },
    lang: "en",
  }),
}));

// Mock ConfirmDialog
jest.mock("@/components/ConfirmDialog", () => ({
  useConfirm: () => ({
    confirm: jest.fn(() => Promise.resolve(true)),
    ConfirmDialog: () => null,
  }),
}));

// Hoisting-safe api mock
jest.mock("@/App", () => {
  const mockApi = {
    get: jest.fn(() => Promise.resolve({ data: {} })),
    post: jest.fn(() => Promise.resolve({ data: {} })),
    put: jest.fn(() => Promise.resolve({ data: {} })),
    delete: jest.fn(() => Promise.resolve({ data: {} })),
  };
  return { api: mockApi };
});
jest.mock("@/lib/api", () => ({
  api: {
    get: jest.fn(() => Promise.resolve({ data: {} })),
    post: jest.fn(() => Promise.resolve({ data: {} })),
  },
  API: "http://test/api",
  BACKEND_URL: "http://test",
}));

import { Sidebar } from "@/components/Sidebar";
import { api } from "@/App";

const defaultProps = {
  workspace: { workspace_id: "ws_123", name: "Test Workspace", type: "personal" },
  channels: [
    { channel_id: "ch_1", name: "general", ai_agents: ["claude", "chatgpt"] },
    { channel_id: "ch_2", name: "design", ai_agents: ["gemini"] },
  ],
  selectedChannel: null,
  onSelectChannel: jest.fn(),
  onCreateChannel: jest.fn(),
  onRefreshChannels: jest.fn(),
  user: { name: "Test User", platform_role: "super_admin" },
  activeTab: "chat",
  onTabChange: jest.fn(),
  projectRefreshKey: 0,
  collapsed: false,
  onToggleCollapse: jest.fn(),
};

describe("Sidebar", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    api.get.mockImplementation((url) => {
      if (url.includes("/agents")) return Promise.resolve({ data: { agents: [] } });
      if (url.includes("/projects")) return Promise.resolve({ data: [] });
      return Promise.resolve({ data: {} });
    });
  });

  describe("rendering", () => {
    it("renders sidebar with test id", () => {
      render(<Sidebar {...defaultProps} />);
      expect(screen.getByTestId("sidebar")).toBeInTheDocument();
    });

    it("displays workspace name", () => {
      render(<Sidebar {...defaultProps} />);
      expect(screen.getByTestId("workspace-name")).toHaveTextContent("Test Workspace");
    });

    it("shows channel list", () => {
      render(<Sidebar {...defaultProps} />);
      expect(screen.getByTestId("channel-item-ch_1")).toBeInTheDocument();
      expect(screen.getByTestId("channel-item-ch_2")).toBeInTheDocument();
    });

    it("shows empty state when no channels", () => {
      render(<Sidebar {...defaultProps} channels={[]} />);
      expect(screen.getByText("No channels yet")).toBeInTheDocument();
    });

    it("renders create channel button", () => {
      render(<Sidebar {...defaultProps} />);
      expect(screen.getByTestId("create-channel-btn")).toBeInTheDocument();
    });
  });

  describe("channel selection", () => {
    it("calls onSelectChannel when clicking a channel", async () => {
      const user = userEvent.setup();
      render(<Sidebar {...defaultProps} />);
      await user.click(screen.getByTestId("channel-item-ch_1"));
      expect(defaultProps.onSelectChannel).toHaveBeenCalledWith(defaultProps.channels[0]);
    });
  });

  describe("navigation", () => {
    it("navigates to dashboard on back button click", async () => {
      const user = userEvent.setup();
      render(<Sidebar {...defaultProps} />);
      await user.click(screen.getByTestId("back-to-dashboard"));
      expect(mockNavigate).toHaveBeenCalledWith("/dashboard");
    });

    it("navigates to settings", async () => {
      const user = userEvent.setup();
      render(<Sidebar {...defaultProps} />);
      await user.click(screen.getByTestId("settings-link"));
      expect(mockNavigate).toHaveBeenCalledWith("/settings");
    });

    it("shows billing link for admin users", () => {
      render(<Sidebar {...defaultProps} />);
      expect(screen.getByTestId("billing-link")).toBeInTheDocument();
    });

    it("hides billing link for non-admin users", () => {
      render(
        <Sidebar {...defaultProps} user={{ name: "Member", platform_role: "member" }} />
      );
      expect(screen.queryByTestId("billing-link")).not.toBeInTheDocument();
    });
  });

  describe("collapse", () => {
    it("calls onToggleCollapse when toggle clicked", async () => {
      const user = userEvent.setup();
      render(<Sidebar {...defaultProps} />);
      await user.click(screen.getByTestId("sidebar-toggle"));
      expect(defaultProps.onToggleCollapse).toHaveBeenCalled();
    });

    it("hides channel names when collapsed", () => {
      render(<Sidebar {...defaultProps} collapsed={true} />);
      expect(screen.queryByText("general")).not.toBeInTheDocument();
      expect(screen.queryByText("design")).not.toBeInTheDocument();
    });

    it("hides workspace name when collapsed", () => {
      render(<Sidebar {...defaultProps} collapsed={true} />);
      expect(screen.queryByTestId("workspace-name")).not.toBeInTheDocument();
    });
  });

  describe("logout", () => {
    it("renders logout button", () => {
      render(<Sidebar {...defaultProps} />);
      expect(screen.getByTestId("sidebar-logout-btn")).toBeInTheDocument();
    });
  });
});
