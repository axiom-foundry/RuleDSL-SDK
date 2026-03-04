# RuleDSL — Pricing & Licensing

## Licensing Model

RuleDSL is licensed per-organization on an annual basis.
Each license covers a defined deployment scope and includes support at the selected tier.

## Tiers

### Starter

For teams evaluating or deploying to a single application.

| Item | Included |
|------|----------|
| Deployment scope | 1 application, 1 platform (Windows or Linux x64) |
| SDK delivery | Versioned artifact packet (headers + binary + docs) |
| Updates | Patch releases for the licensed MAJOR.MINOR line |
| Support | Email, Sev3 response target (5 business days) |
| Evaluation | 30-day structured evaluation included |

### Professional

For teams with production deployments across multiple applications or platforms.

| Item | Included |
|------|----------|
| Deployment scope | Up to 5 applications, both platforms (Windows + Linux x64) |
| SDK delivery | Versioned artifact packet + determinism evidence bundle |
| Updates | Patch + minor releases for the licensed MAJOR line |
| Support | Email, Sev1-3 response targets (1/3/5 business days) |
| Integration advisory | 4 hours of scheduled technical advisory per year |
| Evaluation | 30-day structured evaluation included |

### Enterprise

For organizations with broad deployment, compliance requirements, or custom needs.

| Item | Included |
|------|----------|
| Deployment scope | Unlimited applications, both platforms |
| SDK delivery | Full artifact packet + evidence bundle + signed releases |
| Updates | All releases on the licensed MAJOR line + early access to next MAJOR |
| Support | Priority email, Sev1-3 response targets (1/3/5 business days) |
| Integration advisory | 8 hours of scheduled technical advisory per year |
| Custom | Language binding support, extended conformance evidence |
| Evaluation | 30-day structured evaluation included |

## What is NOT included (any tier)

- 24/7 on-call support (available as a separate add-on)
- Custom engine modifications
- Managed hosting or SaaS operation
- On-site consulting (available separately)

## Evaluation Period

All tiers include a 30-day evaluation at no cost.
During evaluation, the full SDK functionality is available.
Evaluation terms are defined in [`EVALUATION_TERMS.md`](../EVALUATION_TERMS.md).

The evaluation process follows the structured playbook in [`docs/evaluation_playbook.md`](evaluation_playbook.md).

## How to Start

1. Request an evaluation packet via the contact information below
2. Complete the 30-day structured evaluation
3. Review the commercial handoff checklist ([`docs/commercial_handoff.md`](commercial_handoff.md))
4. Select a tier and sign the license agreement

## Contact

For evaluation requests and pricing inquiries:

- GitHub: [github.com/axiom-foundry/RuleDSL-SDK](https://github.com/axiom-foundry/RuleDSL-SDK)
- Email: See repository contact information

## FAQ

**Can I switch tiers later?**
Yes. Tier upgrades take effect at the next billing cycle or immediately upon request.

**What happens when my license expires?**
The SDK continues to function (no kill-switch). You lose access to updates and support.
Renewal restores full access to the current release line.

**Do you offer multi-year discounts?**
Yes. Contact us for 2-year and 3-year pricing.

**Is there a per-seat or per-CPU charge?**
No. Licensing is per-organization, scoped by application count and platform.

**Can I redistribute the SDK to my customers?**
Not under standard tiers. Redistribution licensing is available separately under Enterprise.
