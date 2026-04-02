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

// Mock MFAChallenge
jest.mock("@/components/MFAChallenge", () => {
  return function MockMFAChallenge({ email, onSuccess, onBack }) {
    return (
      <div data-testid="mfa-challenge">
        <span>MFA for {email}</span>
        <button onClick={() => onSuccess({ name: "Test" })} data-testid="mfa-verify-btn">Verify</button>
        <button onClick={onBack} data-testid="mfa-back-btn">Back</button>
      </div>
    );
  };
});

// Mock LanguageContext
jest.mock("@/contexts/LanguageContext", () => ({
  useLanguage: () => ({
    t: (key) => {
      const translations = {
        "common.back": "Back",
        "common.loading": "Loading...",
        "common.email": "Email",
        "auth.signIn": "Sign In",
        "auth.signUp": "Sign Up",
        "auth.company": "Company",
        "auth.createAccount": "Create Account",
        "auth.namePlaceholder": "Your name",
        "auth.passwordPlaceholder": "Password",
        "auth.companySignup": "Register your organization",
        "auth.companyName": "Company Name",
        "auth.yourLoginUrl": "Your login URL:",
        "auth.adminAccount": "Admin Account",
        "auth.yourName": "Your Name",
        "auth.adminEmail": "Admin Email",
        "auth.createOrganization": "Create Organization",
        "auth.creatingOrganization": "Creating...",
      };
      return translations[key] || key;
    },
    lang: "en",
  }),
}));

// Mock LanguageToggle component
jest.mock("@/components/LanguageToggle", () => ({
  LanguageToggle: () => null,
}));

// Hoisting-safe api mock
jest.mock("@/App", () => {
  const mockApi = {
    get: jest.fn(() => Promise.reject({ response: { status: 401 } })),
    post: jest.fn(() => Promise.resolve({ data: {} })),
  };
  return { api: mockApi };
});
jest.mock("@/lib/api", () => ({
  api: {
    get: jest.fn(() => Promise.reject({ response: { status: 401 } })),
    post: jest.fn(() => Promise.resolve({ data: {} })),
  },
  markRecentAuth: jest.fn(),
  API: "http://test/api",
  BACKEND_URL: "http://test",
}));

import AuthPage from "@/pages/AuthPage";
import { api } from "@/App";

describe("AuthPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Default: /auth/me returns 401 (not logged in)
    api.get.mockRejectedValue({ response: { status: 401 } });
    api.post.mockResolvedValue({ data: {} });
  });

  const renderAuth = () => render(<AuthPage />);

  describe("rendering", () => {
    it("renders auth page with test ids", () => {
      renderAuth();
      expect(screen.getByTestId("auth-page")).toBeInTheDocument();
    });

    it("renders login tab by default", () => {
      renderAuth();
      expect(screen.getByTestId("login-tab")).toBeInTheDocument();
      expect(screen.getByTestId("register-tab")).toBeInTheDocument();
      expect(screen.getByTestId("company-tab")).toBeInTheDocument();
    });

    it("shows email and password inputs on login tab", () => {
      renderAuth();
      expect(screen.getByTestId("email-input")).toBeInTheDocument();
      expect(screen.getByTestId("password-input")).toBeInTheDocument();
    });

    it("shows login submit button", () => {
      renderAuth();
      expect(screen.getByTestId("login-submit-btn")).toBeInTheDocument();
    });

    it("shows Google login button", () => {
      renderAuth();
      expect(screen.getByTestId("google-login-btn")).toBeInTheDocument();
    });

    it("shows forgot password button", () => {
      renderAuth();
      expect(screen.getByTestId("forgot-password-btn")).toBeInTheDocument();
    });
  });

  describe("tab switching", () => {
    it("switches to register tab and shows name input", async () => {
      const user = userEvent.setup();
      renderAuth();
      await user.click(screen.getByTestId("register-tab"));
      expect(screen.getByTestId("name-input")).toBeInTheDocument();
      expect(screen.getByTestId("register-email-input")).toBeInTheDocument();
      expect(screen.getByTestId("register-password-input")).toBeInTheDocument();
      expect(screen.getByTestId("tos-checkbox")).toBeInTheDocument();
    });

    it("switches to company tab and shows company fields", async () => {
      const user = userEvent.setup();
      renderAuth();
      await user.click(screen.getByTestId("company-tab"));
      expect(screen.getByTestId("company-name-input")).toBeInTheDocument();
      expect(screen.getByTestId("company-slug-input")).toBeInTheDocument();
    });
  });

  describe("login flow", () => {
    it("disables login button when fields are empty", () => {
      renderAuth();
      expect(screen.getByTestId("login-submit-btn")).toBeDisabled();
    });

    it("enables login button when email and password provided", async () => {
      const user = userEvent.setup();
      renderAuth();
      await user.type(screen.getByTestId("email-input"), "test@test.com");
      await user.type(screen.getByTestId("password-input"), "password123");
      expect(screen.getByTestId("login-submit-btn")).not.toBeDisabled();
    });

    it("calls login API on submit", async () => {
      const user = userEvent.setup();
      api.post.mockResolvedValueOnce({ data: { name: "Test User" } });
      renderAuth();

      await user.type(screen.getByTestId("email-input"), "test@test.com");
      await user.type(screen.getByTestId("password-input"), "password");
      await user.click(screen.getByTestId("login-submit-btn"));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith("/auth/login", {
          email: "test@test.com",
          password: "password",
        });
      });
    });

    it("shows error on login failure", async () => {
      const user = userEvent.setup();
      api.post.mockRejectedValueOnce({
        response: { data: { detail: "Invalid credentials" } },
      });
      renderAuth();

      await user.type(screen.getByTestId("email-input"), "bad@test.com");
      await user.type(screen.getByTestId("password-input"), "wrong");
      await user.click(screen.getByTestId("login-submit-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("auth-error")).toBeInTheDocument();
        expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
      });
    });

    it("shows MFA challenge when mfa_required is true", async () => {
      const user = userEvent.setup();
      // Override default post mock for entire test
      api.post.mockResolvedValue({
        data: { mfa_required: true, email: "mfa@test.com" },
      });
      renderAuth();

      await user.type(screen.getByTestId("email-input"), "mfa@test.com");
      await user.type(screen.getByTestId("password-input"), "password");
      await user.click(screen.getByTestId("login-submit-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("mfa-challenge")).toBeInTheDocument();
      });
    });
  });

  describe("register flow", () => {
    it("disables register button without TOS acceptance", async () => {
      const user = userEvent.setup();
      renderAuth();
      await user.click(screen.getByTestId("register-tab"));
      await user.type(screen.getByTestId("name-input"), "Test");
      await user.type(screen.getByTestId("register-email-input"), "t@t.com");
      await user.type(screen.getByTestId("register-password-input"), "pass");
      expect(screen.getByTestId("register-submit-btn")).toBeDisabled();
    });

    it("enables register button with all fields and TOS", async () => {
      const user = userEvent.setup();
      renderAuth();
      await user.click(screen.getByTestId("register-tab"));
      await user.type(screen.getByTestId("name-input"), "Test");
      await user.type(screen.getByTestId("register-email-input"), "t@t.com");
      await user.type(screen.getByTestId("register-password-input"), "pass");
      await user.click(screen.getByTestId("tos-checkbox"));
      expect(screen.getByTestId("register-submit-btn")).not.toBeDisabled();
    });
  });
});
