# picks
Owns: scoring candidates in plain code (`shortlist` → details → `rank`, top 15), building the local model's prompt + JSON schema (`messages`, `schema`), and `check`ing its reply into 3 `Pick`s (one per slot).
Must not: touch the network, SQL or files. Never trusts the model: ids outside the batch, repeats and reasons that name nothing shared are replaced by plain code; `check({}, candidates)` = 3 plain-code picks.
Shapes: `TitleInfo` / `Title` in, `Candidate` / `Pick` out (see `curator.model`).
