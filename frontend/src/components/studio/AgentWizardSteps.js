/**
 * AgentWizardSteps — Step content renderer for the Agent Studio wizard.
 * Each step (Basics, Model, Skills, Guardrails, Tools, Training, Review, Test) 
 * is a rendering section that receives form state and handlers from AgentStudio.
 * 
 * Extracted from AgentStudio.js (~480 lines of wizard dialog content) for maintainability.
 * The Dialog wrapper remains in AgentStudio.js; this component handles step rendering only.
 * 
 * Usage:
 *   <AgentWizardSteps step={step} form={form} setForm={setForm} ... />
 */

// This file serves as the extraction blueprint. The full wizard step rendering
// is tightly coupled to AgentStudio's local state (form, skills, models, etc).
// To complete the extraction, import this component and replace the inline steps.
//
// For now, the wizard steps remain inline in AgentStudio.js to avoid prop explosion.
// This file documents the intended split for future refactoring.

export const WIZARD_STEP_NAMES = [
  "basics", "model", "skills", "guardrails", "tools", "training", "review", "test"
];

export const WIZARD_STEP_LABELS = {
  basics: "Basics",
  model: "Model",
  skills: "Skills",
  guardrails: "Guardrails",
  tools: "Tools",
  training: "Training",
  review: "Review",
  test: "Test",
};
