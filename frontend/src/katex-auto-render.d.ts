declare module "katex/contrib/auto-render" {
  import type { KatexOptions } from "katex";

  interface DelimiterSpec {
    left: string;
    right: string;
    display: boolean;
  }

  interface RenderMathInElementOptions extends KatexOptions {
    delimiters?: DelimiterSpec[];
    errorCallback?: (message: string, error: Error) => void;
    ignoredClasses?: string[];
    ignoredTags?: string[];
    preProcess?: (math: string) => string;
  }

  export default function renderMathInElement(
    element: HTMLElement,
    options?: RenderMathInElementOptions,
  ): void;
}
