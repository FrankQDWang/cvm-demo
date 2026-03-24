# Product Requirements Summary

This repository implements the MVP loop defined by the source PRD:

1. Create `JDCase`
2. Freeze a `JDVersion`
3. Generate a keyword draft and `ConditionPlan`
4. Confirm the plan
5. Start a `SearchRun`
6. Persist page snapshots and candidate records
7. Open candidate detail and submit a verdict
8. Export masked candidate data and audit the action

Non-goals in this repository stage:

- No cloud deployment
- No vector retrieval
- No autonomous final verdict
- No browser automation as the primary search path
