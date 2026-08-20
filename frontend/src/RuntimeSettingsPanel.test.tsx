import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import RuntimeSettingsPanel from "./RuntimeSettingsPanel";
import type { ModelOption, RuntimeOptions, RuntimeSettings } from "./types";

const settings: RuntimeSettings = {
  model_name: "gpt-5.6-luna",
  temperature: 0.1,
  top_p: 0.9,
  max_steps: 4,
  timeout_seconds: 300,
  db_rag_embedding_model: "OpenAI/text-embedding-3-large",
  db_rag_reranker_model: "disabled",
};

function modelOption(
  id: string,
  label: string,
  reasoning_tier: ModelOption["reasoning_tier"],
): ModelOption {
  return {
    id,
    label,
    provider: "openai",
    provider_label: "OpenAI",
    reasoning_tier,
    summary: `${label} guidance.`,
    initial_output_tokens: 8_192,
    automatic_output_token_ceiling: 16_384,
    user_output_token_increment: 8_192,
    absolute_output_token_ceiling: 24_576,
    request_timeout_seconds: 120,
    workflow_timeout_seconds: 300,
    automatic_output_cost: "$0.02",
    incremental_output_cost: "$0.01",
  };
}

const options: RuntimeOptions = {
  defaults: settings,
  capabilities: {
    publication_knowledge: {
      status: "available",
      message: "Publication knowledge is available.",
    },
    db_rag_dataset: {
      status: "not_configured",
      message: "Copy the optional DB-RAG assets to enable dataset querying.",
    },
  },
  models: [
    modelOption("gpt-5.4", "gpt-5.4 (Standard)", "standard"),
    modelOption("gpt-5.6-luna", "gpt-5.6-luna (Low)", "low"),
    modelOption("gpt-5.6-terra", "gpt-5.6-terra (Medium)", "medium"),
    modelOption("gpt-5.6-sol", "gpt-5.6-sol (Medium)", "medium"),
  ],
};

describe("RuntimeSettingsPanel", () => {
  it("shows publication knowledge independently from optional DB-RAG", () => {
    render(
      <RuntimeSettingsPanel
        locked={false}
        onChange={vi.fn()}
        options={options}
        settings={settings}
      />,
    );

    expect(screen.getByText("Publication knowledge: Available"))
      .toBeInTheDocument();
    expect(screen.getByText("DB-RAG dataset: Not configured"))
      .toBeInTheDocument();
    expect(screen.queryByLabelText("Provider")).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "Copy the optional DB-RAG assets to enable dataset querying.",
      ),
    ).toBeInTheDocument();
  });

  it("reports editable model and temperature changes", () => {
    const onChange = vi.fn();
    render(
      <RuntimeSettingsPanel
        locked={false}
        onChange={onChange}
        options={options}
        settings={settings}
      />,
    );

    fireEvent.change(screen.getByLabelText("Model"), {
      target: { value: "gpt-5.6-luna" },
    });
    expect(onChange).toHaveBeenLastCalledWith({
      ...settings,
      model_name: "gpt-5.6-luna",
    });

    fireEvent.change(screen.getByLabelText("Temperature"), {
      target: { value: "0.2" },
    });
    expect(onChange).toHaveBeenLastCalledWith({
      ...settings,
      temperature: 0.2,
    });
  });

  it("disables locked controls and shows the lock message", () => {
    render(
      <RuntimeSettingsPanel
        locked={true}
        onChange={vi.fn()}
        options={options}
        settings={settings}
      />,
    );

    expect(screen.getByText("Settings are locked for this thread."))
      .toBeInTheDocument();
    expect(screen.getByLabelText("Model")).toBeDisabled();
    expect(screen.getByLabelText("Temperature")).toBeDisabled();
    expect(screen.getByLabelText("Top probability")).toBeDisabled();
    expect(screen.getByLabelText("Auto-run steps")).toBeDisabled();
    expect(screen.getByLabelText("Workflow timeout")).toBeDisabled();
  });

  it("uses a placeholder for an unsupported model value", () => {
    render(
      <RuntimeSettingsPanel
        locked={false}
        onChange={vi.fn()}
        options={options}
        settings={{
          ...settings,
          model_name: "unsupported-model",
        }}
      />,
    );

    expect(screen.getByLabelText("Model")).toHaveValue("");
    expect(screen.getByRole("option", { name: "Select model" })).toBeDisabled();
  });

  it("does not display an unsupported model as selected", () => {
    render(
      <RuntimeSettingsPanel
        locked={false}
        onChange={vi.fn()}
        options={options}
        settings={{
          ...settings,
          model_name: "unsupported-model",
        }}
      />,
    );

    expect(screen.getByLabelText("Model")).toHaveValue("");
  });

  it("ignores invalid numeric values and fractional auto-run steps", () => {
    const onChange = vi.fn();
    render(
      <RuntimeSettingsPanel
        locked={false}
        onChange={onChange}
        options={options}
        settings={settings}
      />,
    );

    fireEvent.change(screen.getByLabelText("Temperature"), {
      target: { value: "Infinity" },
    });
    fireEvent.change(screen.getByLabelText("Workflow timeout"), {
      target: { value: "not-a-number" },
    });
    fireEvent.change(screen.getByLabelText("Auto-run steps"), {
      target: { value: "4.5" },
    });

    expect(onChange).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Auto-run steps"), {
      target: { value: "" },
    });
    expect(onChange).toHaveBeenCalledWith({
      ...settings,
      max_steps: null,
    });
  });
});
