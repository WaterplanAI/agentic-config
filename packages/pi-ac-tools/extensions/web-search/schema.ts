import { StringEnum } from "@mariozechner/pi-ai";
import { Type } from "@sinclair/typebox";

export const LocationSchema = Type.Object(
  {
    lat: Type.Optional(Type.Number({ description: "Latitude (-90 to 90)" })),
    long: Type.Optional(Type.Number({ description: "Longitude (-180 to 180)" })),
    city: Type.Optional(Type.String({ description: "City for location-aware search" })),
    state: Type.Optional(Type.String({ description: "State or region abbreviation" })),
    state_name: Type.Optional(Type.String({ description: "Full state or region name" })),
    country: Type.Optional(Type.String({ description: "Country for location-aware search" })),
    postal_code: Type.Optional(Type.String({ description: "Postal code for location-aware search" })),
  },
  { additionalProperties: false },
);

export const WebSearchToolSchema = Type.Object(
  {
    q: Type.String({
      minLength: 1,
      maxLength: 400,
      description: "Search query (max 400 chars, max 50 words)",
    }),
    country: Type.Optional(Type.String({ description: "Country hint, e.g. us, gb, de" })),
    search_lang: Type.Optional(Type.String({ description: "Search language hint, e.g. en, de" })),
    count: Type.Optional(Type.Integer({ minimum: 1, maximum: 50, description: "Requested result count (1-50)" })),
    freshness: Type.Optional(Type.String({ description: "Freshness hint, e.g. pd, pw, pm, py, 2026-03-01..2026-03-31" })),
    maximum_number_of_urls: Type.Optional(
      Type.Integer({ minimum: 1, maximum: 50, description: "Max URLs to ground into the result" }),
    ),
    maximum_number_of_tokens: Type.Optional(
      Type.Integer({ minimum: 1024, maximum: 32768, description: "Total grounding token budget" }),
    ),
    maximum_number_of_snippets: Type.Optional(
      Type.Integer({ minimum: 1, maximum: 100, description: "Total snippet budget" }),
    ),
    maximum_number_of_tokens_per_url: Type.Optional(
      Type.Integer({ minimum: 512, maximum: 8192, description: "Per-URL token budget" }),
    ),
    maximum_number_of_snippets_per_url: Type.Optional(
      Type.Integer({ minimum: 1, maximum: 100, description: "Per-URL snippet budget" }),
    ),
    context_threshold_mode: Type.Optional(
      StringEnum(["strict", "balanced", "lenient", "disabled"] as const, {
        description: "Context threshold mode",
      }),
    ),
    enable_local: Type.Optional(Type.Boolean({ description: "Enable local / map grounding when supported" })),
    goggles: Type.Optional(
      Type.Union([
        Type.String({ description: "Single goggles identifier" }),
        Type.Array(Type.String({ minLength: 1 }), { minItems: 1, description: "Multiple goggles identifiers" }),
      ]),
    ),
    location: Type.Optional(LocationSchema),
  },
  { additionalProperties: false },
);
