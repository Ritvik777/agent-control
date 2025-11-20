# Agent Protect Engine

Core logic for executing protection rules.

## Responsibilities

- Extracting data from payloads using `RuleSelector` paths
- Evaluating data against rules using `RuleEvaluator` logic
- Executing regex checks safely using `google-re2`
- Providing a unified `RuleEngine` interface for Server and SDK
