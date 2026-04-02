import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfirmProvider, useConfirm } from "@/components/ConfirmDialog";

// Mock the Radix Dialog to avoid JSDOM rendering issues
jest.mock("@/components/ui/dialog", () => {
  const React = require("react");
  return {
    Dialog: ({ open, onOpenChange, children }) => open ? <div data-testid="mock-dialog">{children}<button data-testid="dialog-backdrop" onClick={() => onOpenChange(false)}>close</button></div> : null,
    DialogContent: ({ children }) => <div>{children}</div>,
    DialogHeader: ({ children }) => <div>{children}</div>,
    DialogTitle: ({ children }) => <h2>{children}</h2>,
    DialogDescription: ({ children }) => <p>{children}</p>,
  };
});

// Mock lucide-react
jest.mock("lucide-react", () => ({
  AlertTriangle: (props) => <span data-testid="alert-icon" />,
}));

// Mock the button component
jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, variant, className }) => (
    <button onClick={onClick} className={className} data-variant={variant}>
      {children}
    </button>
  ),
}));

// Minimal test component that uses useConfirm
function TestConsumer() {
  const { confirm, ConfirmDialog } = useConfirm();

  const handleClick = async () => {
    const result = await confirm("Delete Item", "Are you sure?");
    document.getElementById("result").textContent = result
      ? "confirmed"
      : "cancelled";
  };

  return (
    <div>
      <button onClick={handleClick} data-testid="trigger-btn">
        Trigger
      </button>
      <span id="result" data-testid="result"></span>
      <ConfirmDialog />
    </div>
  );
}

describe("ConfirmDialog", () => {
  describe("ConfirmProvider + useConfirm", () => {
    it("renders children without dialog initially", () => {
      render(
        <ConfirmProvider>
          <TestConsumer />
        </ConfirmProvider>
      );
      expect(screen.getByTestId("trigger-btn")).toBeInTheDocument();
      expect(screen.queryByText("Delete Item")).not.toBeInTheDocument();
    });

    it("opens dialog when confirm is called", async () => {
      const user = userEvent.setup();
      render(
        <ConfirmProvider>
          <TestConsumer />
        </ConfirmProvider>
      );

      await user.click(screen.getByTestId("trigger-btn"));
      expect(screen.getByText("Delete Item")).toBeInTheDocument();
      expect(screen.getByText("Are you sure?")).toBeInTheDocument();
    });

    it("resolves true when Confirm is clicked", async () => {
      const user = userEvent.setup();
      render(
        <ConfirmProvider>
          <TestConsumer />
        </ConfirmProvider>
      );

      await user.click(screen.getByTestId("trigger-btn"));
      // Click the Confirm button
      await user.click(screen.getByText("Confirm"));

      await waitFor(() => {
        expect(screen.getByTestId("result")).toHaveTextContent("confirmed");
      });
    });

    it("resolves false when Cancel is clicked", async () => {
      const user = userEvent.setup();
      render(
        <ConfirmProvider>
          <TestConsumer />
        </ConfirmProvider>
      );

      await user.click(screen.getByTestId("trigger-btn"));
      await user.click(screen.getByText("Cancel"));

      await waitFor(() => {
        expect(screen.getByTestId("result")).toHaveTextContent("cancelled");
      });
    });
  });

  describe("useConfirm outside provider (fallback)", () => {
    it("returns a confirm function that works as fallback", () => {
      function FallbackConsumer() {
        const { confirm, ConfirmDialog } = useConfirm();
        return (
          <div>
            <span data-testid="has-confirm">
              {typeof confirm === "function" ? "yes" : "no"}
            </span>
            <ConfirmDialog />
          </div>
        );
      }

      render(<FallbackConsumer />);
      expect(screen.getByTestId("has-confirm")).toHaveTextContent("yes");
    });
  });
});
