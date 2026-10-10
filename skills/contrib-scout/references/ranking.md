# Ranking rules for contrib-scout

Rank candidate issues from best to worst using these signals, in order:

1. **Label strength** — issues with both `good first issue` and `hacktoberfest`
   rank above issues with only one of them.
2. **Repository activity** — prefer repositories pushed to within the last 30
   days. Stale repos are risky for a first contribution.
3. **Guidance present** — prefer repositories that have a `CONTRIBUTING` file,
   since they document how to submit a PR.
4. **Issue freshness** — newer issues are less likely to be already claimed.
5. **Reasonable scope** — prefer issues whose title suggests a small, concrete
   change (docs, a single function, a test) over broad or vague ones.

For each selected issue, write one line: what it is and why it fits the user's
languages and interests.
