# Source Provenance Trust Boundary

## Problem

The source schema allowed arbitrary analysis JSON to state `provenance: bright_data`, and CLI library imports appended those values directly into analysis reports.

## Solution

- Public pure analysis rejects `bright_data` and `bright_data_transport` provenance.
- The production transport wrapper, tested with a local stub opener, may assign `bright_data_transport` only to its current in-memory result. Injected transports remain `synthetic_fixture`.
- Before JSON export, that invocation-local marker becomes `operator_claimed_bright_data`; importing legacy `bright_data` markers makes the same downgrade.
- A structurally matching receipt is not treated as authentication because local receipt files can be edited.

## Limitation

There is no signing key or persistent authenticated attestation. Exported/imported provider origin is therefore always a self-asserted claim, not verified provider retrieval.
