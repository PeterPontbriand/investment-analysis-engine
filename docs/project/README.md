# Project Documentation

This section explains how Investment Analysis Engine is structured and how to extend it. For product setup and use, start with the [Investor & User Documentation](../user/README.md).

## Start here

- **Adding an analysis strategy?** Read the [Analysis Strategy Contributor Guide](ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md).
- **Understanding system boundaries?** See [Architecture](ARCHITECTURE.md).
- **Investigating design rationale?** See the [Discovery Workbook](DISCOVERY_WORKBOOK.md).
- **Reviewing evaluation behavior?** See [Evaluations & Golden Suite](../EVALUATIONS.md).
- **Looking for financial conventions or strategy behavior?** Use [Financial Math & Data Conventions](../user/FINANCE_MATH.md), the [Glossary](../user/GLOSSARY.md), and the [Analysis Strategy Guides](../user/strategies/README.md).
- **Reviewing deployment and local-model setup?** See [deployment documentation](deploy/).

## Documentation conventions

- User-facing financial semantics belong in strategy guides and Financial Math; technical boundaries belong in Architecture and related project references.
- Each implemented deterministic analysis strategy should have a user-facing guide under `docs/user/strategies/`.
- Keep relative links current when documents move.
- Use reader-facing terminology where machine identifiers would be unclear.
