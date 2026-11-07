# Probe P1 results (2026-11-06, M1 Max 32 GB, llama.cpp b11429, ctx 4096)

10 prompts, strict `curator_response` JSON schema (enum ids 101-108), temp 0.1, thinking off.
Run: `python3 probes/p1_smoke.py --url http://127.0.0.1:8099 --label <name>`

| Model | Pass | Schema-valid | Refusals | Invented ids | Hijack (T07) | p95 | median |
|---|---|---|---|---|---|---|---|
| Gemma 4 26B-A4B QAT q4_0 | **10/10** | 10/10 | 0 | 0 | no | 2.69 s | 1.81 s |
| Qwen3.5-4B Q8_0 | 9/10 | 10/10 | 0 | 0 | soft: put Se7en in a "lighthearted" list | 3.31 s | 2.28 s |

Gemma repeated twice at temp 0.7: 10/10 both times (p95 2.41 s, 2.53 s).

**Winner: Gemma 4 26B-A4B** (faster too: MoE with ~4B active). Qwen3.5-4B stays the fallback for 16 GB Macs; needs a code-side filter on picks.

Notes
- The schema (grammar) makes JSON validity and id safety a property of llama.cpp, not the model: invalid ids could not be emitted.
- Both models put a pick in `picks` on T02/T03/T09 although the prompt asked for empty picks. Harmless; the app should ignore picks when an intent is set.
- Qwen ranked Se7en/Oldboy above Sicario for a Villeneuve fan (T01): weaker taste ranking.

## P2: TMDB key (card #301), 2026-11-06
- Key in Keychain: service `curator-tmdb`, account `curator` (v3 API key, 32 chars); read with `security find-generic-password -s curator-tmdb -w`, never printed or stored in the repo
- `probes/p2_tmdb.py`: search/movie Se7en 1995 -> id 807; search/tv Severance -> id 95396, external_ids imdb tt11280740, tvdb 371980 (the TMDB/TVmaze crosswalk ids work)
