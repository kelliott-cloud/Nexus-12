import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock sonner
jest.mock("sonner", () => ({
  toast: { error: jest.fn(), success: jest.fn(), info: jest.fn() },
  Toaster: () => null,
}));

// We test errorHandler directly without mocking it
// But we need to mock the api import inside errorHandler
jest.mock("@/App", () => ({
  api: { post: jest.fn(() => Promise.resolve()) },
}));

import { handleError, handleSilent, handleCritical, reportError } from "@/lib/errorHandler";
import { toast } from "sonner";

describe("errorHandler", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    jest.spyOn(console, "warn").mockImplementation(() => {});
  });

  afterEach(() => {
    console.error.mockRestore();
    console.warn.mockRestore();
  });

  describe("handleError", () => {
    it("logs error with context", () => {
      const err = new Error("test failure");
      handleError(err, "TestComponent");
      expect(console.error).toHaveBeenCalledWith(
        "[Nexus Error] TestComponent:",
        err
      );
    });

    it("shows toast with error message", () => {
      const err = new Error("something broke");
      handleError(err, "TestCtx");
      expect(toast.error).toHaveBeenCalledWith("something broke");
    });

    it("extracts detail from API errors", () => {
      const err = { response: { data: { detail: "API validation error" } } };
      handleError(err, "APITest");
      expect(toast.error).toHaveBeenCalledWith("API validation error");
    });

    it("falls back to generic message", () => {
      handleError({}, "fallback");
      expect(toast.error).toHaveBeenCalledWith("Something went wrong");
    });
  });

  describe("handleSilent", () => {
    it("logs warning without toast", () => {
      const err = new Error("silent issue");
      handleSilent(err, "SilentCtx");
      expect(console.warn).toHaveBeenCalledWith(
        "[Nexus Warning] SilentCtx:",
        "silent issue"
      );
      expect(toast.error).not.toHaveBeenCalled();
    });
  });

  describe("handleCritical", () => {
    it("logs critical error and shows long-duration toast", () => {
      const err = new Error("critical failure");
      handleCritical(err, "CriticalCtx");
      expect(console.error).toHaveBeenCalledWith(
        "[Nexus CRITICAL] CriticalCtx:",
        err
      );
      expect(toast.error).toHaveBeenCalledWith("critical failure", {
        duration: 10000,
      });
    });
  });

  describe("reportError", () => {
    it("does not throw when called", () => {
      expect(() =>
        reportError("manual error", { component: "ManualTest" })
      ).not.toThrow();
    });
  });
});
