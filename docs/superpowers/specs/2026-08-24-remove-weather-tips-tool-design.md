# Remove Seasonal Weather Tips Tool

Date: 2026-08-24
Status: Approved design

## Goal

Remove the `general-get_weather_tips` capability completely while preserving
the independent `general-query_weather` capability for live current conditions
and bounded forecasts.

## Scope

The removal covers every live layer owned by the seasonal tips capability:

- Delete `GetWeatherTipsTool` and its registry entry.
- Delete the weather MCP server's `get_weather_tips` operation.
- Delete the API activity label for `general-get_weather_tips`.
- Update registry contract coverage so the removed tool is explicitly absent
  and `general-query_weather` remains present.
- Add a dedicated backend smoke script that exercises the production registry
  boundary and verifies the same presence and absence conditions.

Historical design and plan documents remain unchanged because they describe
the repository at the time they were written.

## Architecture and Data Flow

The general tool registry will no longer publish a schema named
`general-get_weather_tips`. Consequently, the model cannot request that tool
and the runtime cannot dispatch it. The weather MCP server will continue to
provide `query_weather`, backed by Open-Meteo, without changes to its inputs,
output, or error behavior.

No replacement or fallback is introduced. General seasonal advice can still
be written from ordinary model knowledge when appropriate, but it will not be
represented as live weather evidence.

## Error Handling

There is no new runtime error path. A stale caller attempting
`general-get_weather_tips` will encounter the existing unknown-tool handling
because the capability is no longer registered. Current and forecast weather
requests retain the existing MCP error handling through `general-query_weather`.

## Testing

Development follows a red-green cycle:

1. Change the registry contract test to require `general-get_weather_tips` to
   be absent while requiring `general-query_weather` to remain present, and
   observe it fail against the current implementation.
2. Remove the production capability and observe the focused test pass.
3. Run the relevant registry and activity-label tests.
4. Run a dedicated backend smoke script through the production registry
   construction boundary. The smoke must complete once within five minutes.

## Non-Goals

- Removing or changing `general-query_weather`.
- Removing the weather MCP server itself.
- Enabling OpenAI built-in web search or changing Tavily search.
- Changing prompts, frontend behavior, model profiles, or environment values.
