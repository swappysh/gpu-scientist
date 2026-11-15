cells/<commit>.json: one row per scored dev cell: [series_id, origin (date ordinal), h, truth, last price at origin, [q10, q50, q90], pinball loss, flat (last-value) loss]. Skill on a set of cells = 1 - sum(loss) / sum(flat loss).
Key models: incumbent 18c491e, pick b06b208, pick's parent 19a5148. cells/ also holds every chain step.
chain.txt: each step from the incumbent to the pick, its parent and its commit message.
forecasters/<commit>.py: each step's forecaster.
moves.txt: how often prices moved, by source and period.
