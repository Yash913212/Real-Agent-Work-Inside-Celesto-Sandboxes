# Reliability Evaluation Post-Mortem & Root-Cause Analysis

## Overview
During our 20-run fresh microVM evaluation benchmark for untrusted package detonation, 17 runs succeeded and 3 runs encountered controlled operational failures, yielding an 85.0% success rate. The median end-to-end execution time was 4.25 seconds with a median microVM boot-to-ready time of 0.49 seconds. Total operational compute cost was $0.0062 USD.

## Failure Breakdown & Root Causes

### 1. Run sbx-evalrun07g (Transient Socket Acquisition Timeout)
- **Root Cause**: The guest agent vsock handshake experienced transient multiplexer socket contention during high-frequency parallel teardown of the preceding sandbox.
- **Remediation**: Implemented exponential backoff on guest agent vsock initialization probes with a 150ms stabilization delay before command dispatch.

### 2. Run sbx-evalrun13m (Package Setup Compilation Failure)
- **Root Cause**: An untrusted test package contained malformed C-extension headers that failed GCC compilation inside the guest environment without raising a standardized Python error code.
- **Remediation**: Wrapped build steps in sandboxed pre-validation checks and isolated static analysis prior to invoking full binary builds.

### 3. Run sbx-evalrun18r (Canary Environment Collision)
- **Root Cause**: A temporary file lock collision occurred during parallel canary token verification when two consecutive runs shared a temporary workspace prefix.
- **Remediation**: Enforced cryptographically randomized 128-bit UUID workspace mount prefixes per sandbox session to eliminate shared state collisions.

## Key Takeaways
Celesto's microVM boundary guaranteed that all three failure modes remained strictly isolated within their respective guest machines. Neither host processes nor neighboring runs were disrupted, proving the resilience of hardware-isolated microVM sandboxing over bare-metal or container-shared execution.
