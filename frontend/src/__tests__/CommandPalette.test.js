import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock sonner
jest.mock("sonner", () => ({
  toast: { error: jest.fn(), success: jest.fn() },
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

// Use inline mocks for api - hoisting safe
jest.mock("@/App", () => {
  const mockApi = {
    get: jest.fn(() => Promise.resolve({ data: {} })),
  };
  return { api: mockApi };
});
jest.mock("@/lib/api", () => ({
  api: { get: jest.fn(() => Promise.resolve({ data: {} })) },
  API: "http://test/api",
  BACKEND_URL: "http://test",
}));

import CommandPalette from "@/components/CommandPalette";
import { api } from "@/App";

describe("CommandPalette", () => {
  const mockOnNavigate = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("keyboard activation", () => {
    it("does not render palette initially", () => {
      render(<CommandPalette onNavigate={mockOnNavigate} />);
      expect(screen.queryByTestId("command-palette")).not.toBeInTheDocument();
    });

    it("opens on Ctrl+K", async () => {
      render(<CommandPalette onNavigate={mockOnNavigate} />);
      const user = userEvent.setup();
      await user.keyboard("{Control>}k{/Control}");
      expect(screen.getByTestId("command-palette")).toBeInTheDocument();
    });

    it("closes on Escape", async () => {
      render(<CommandPalette onNavigate={mockOnNavigate} />);
      const user = userEvent.setup();
      await user.keyboard("{Control>}k{/Control}");
      expect(screen.getByTestId("command-palette")).toBeInTheDocument();
      await user.keyboard("{Escape}");
      expect(screen.queryByTestId("command-palette")).not.toBeInTheDocument();
    });
  });

  describe("command listing", () => {
    it("shows all commands when opened", async () => {
      render(<CommandPalette onNavigate={mockOnNavigate} />);
      const user = userEvent.setup();
      await user.keyboard("{Control>}k{/Control}");

      expect(screen.getByTestId("cmd-chat")).toBeInTheDocument();
      expect(screen.getByTestId("cmd-projects")).toBeInTheDocument();
      expect(screen.getByTestId("cmd-tasks")).toBeInTheDocument();
      expect(screen.getByTestId("cmd-docs")).toBeInTheDocument();
      expect(screen.getByTestId("cmd-settings")).toBeInTheDocument();
    });

    it("filters commands by query", async () => {
      render(<CommandPalette onNavigate={mockOnNavigate} />);
      const user = userEvent.setup();
      await user.keyboard("{Control>}k{/Control}");

      // Type single char (stays in command mode)
      await user.type(screen.getByTestId("command-input"), "w");

      // Should show "Workflows" and "Walkthroughs" etc
      expect(screen.getByTestId("cmd-workflows")).toBeInTheDocument();
    });
  });

  describe("navigation", () => {
    it("calls onNavigate with tab when command selected", async () => {
      render(<CommandPalette onNavigate={mockOnNavigate} />);
      const user = userEvent.setup();
      await user.keyboard("{Control>}k{/Control}");

      await user.click(screen.getByTestId("cmd-projects"));
      expect(mockOnNavigate).toHaveBeenCalledWith("projects");
    });

    it("navigates to settings path", async () => {
      render(<CommandPalette onNavigate={mockOnNavigate} />);
      const user = userEvent.setup();
      await user.keyboard("{Control>}k{/Control}");

      await user.click(screen.getByTestId("cmd-settings"));
      expect(mockNavigate).toHaveBeenCalledWith("/settings");
    });

    it("closes palette after selection", async () => {
      render(<CommandPalette onNavigate={mockOnNavigate} />);
      const user = userEvent.setup();
      await user.keyboard("{Control>}k{/Control}");
      expect(screen.getByTestId("command-palette")).toBeInTheDocument();

      await user.click(screen.getByTestId("cmd-chat"));
      expect(screen.queryByTestId("command-palette")).not.toBeInTheDocument();
    });
  });

  describe("search mode", () => {
    it("switches to search mode when typing 2+ chars", async () => {
      api.get.mockResolvedValue({ data: { results: [] } });
      render(<CommandPalette onNavigate={mockOnNavigate} />);
      const user = userEvent.setup();
      await user.keyboard("{Control>}k{/Control}");

      await user.type(screen.getByTestId("command-input"), "te");

      await waitFor(() => {
        expect(screen.getByTestId("cmd-mode-search")).toBeInTheDocument();
      });
    });
  });
});
