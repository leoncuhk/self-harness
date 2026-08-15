/** Frozen OpenAI-compatible provider route for the beneficiary model. */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function registerSelfHarnessProvider(pi: ExtensionAPI) {
	const baseUrl = process.env.OPENAI_BASE_URL;
	if (!baseUrl) {
		throw new Error("OPENAI_BASE_URL is required for the self-harness provider");
	}
	pi.registerProvider("self-harness", {
		baseUrl,
		apiKey: "OPENAI_API_KEY",
		api: "openai-completions",
		authHeader: true,
		models: [
			{
				id: "deepseek-v4-flash",
				name: "DeepSeek V4 Flash",
				reasoning: false,
				input: ["text"],
				contextWindow: 131072,
				maxTokens: 32768,
				cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
				compat: {
					supportsDeveloperRole: false,
					supportsReasoningEffort: false,
					maxTokensField: "max_tokens",
				},
			},
		],
	});
}
