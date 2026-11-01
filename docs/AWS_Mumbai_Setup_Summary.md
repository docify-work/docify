# AWS setup: $200 credits + Mumbai (done 2026-11-01)

This follows `docs/pdf/aws_mumbai_region_final_plan.pdf`. All 7 steps are complete.

## What was done

| # | Step | Result |
|---|---|---|
| 1 | Free Plan, $100 | ✅ |
| 2 | Earn the other $100 (5 "Explore AWS" activities) | ✅ Budgets, Lambda URL, EC2, RDS and Bedrock playground were each done once, then the test resources were deleted |
| 3 | Check credits | ✅ $200: $100 expires **2027-10-12**, $100 expires **2027-10-30** |
| 4 | Upgrade to Paid plan | ✅ Card added (the ₹2 verification charge is refunded) |
| 5 | Activate advanced features | ✅ Org `Docify-Team`, management email docify.work@gmail.com. **Irreversible; the spend limit was removed** |
| 6 | Unlock Mumbai | ✅ Added `ap-south-1` to the `RegionFloor` statement of the org SCP `AdvancedModeRegionRestrictionSecurityControlPolicy` |
| 7 | Check credits again | ✅ $200 remaining, $0 used (credits now sit in the management account) |

## How it fits together now

- **Org `Docify-Team`:** the management account (billing and credits), the `Docify` project account (where we build, in ap-south-1), and an Identity Delegated Admin account.
- **CLI profiles:** `docify` (project account, region ap-south-1) and `docify-mgmt` (management account). If a session expires, run `aws login --profile <name>` and pick the matching session in the browser.
- **Live AWS resources:** Phase 8 infrastructure in Mumbai (see Master Doc §1). The server `docify-server` (t4g.large, ~$0.05/h while running) is **stopped when idle** and auto-stops at 23:00 IST.

## Protecting the credit card

The goal is **$0 on the card**. Since step 5 there is **no hard spend cap**, so these are what protect it:

| Guard | Where | What it does |
|---|---|---|
| `docify-credit-burn` budget | management account | Emails when credit use (counted before credits) passes $1, $50, $150 or $180, or when it's forecast to pass $200 |
| `docify-card-charge` budget | management account | Emails if **anything** is billed after credits (> $0.01), so the card is being charged |
| `docify-server-autostop` budget + `docify-budgets-action-role` | Docify account | **Stops the server automatically** at $180 used (before credits). `docify-spend-freeze` policy kept for later CI-role freezes |

⚠ **Ways the card could still be charged:**
1. Total usage goes past $200.
2. Items credits don't cover: Route 53 domain registration, Marketplace, support plans, Savings Plans/RIs, and possibly tax.
3. Usage after the credits expire (Oct 2027).
4. Billing data lags 8–24 h, so alerts can arrive after money has already been spent.

## Still open

- ✅ **Stop-server action wired (2026-11-01):** budget `docify-server-autostop` in the Docify account (usage before credits, $200 window) stops the server automatically at **90 % = $180** and emails. It pins the instance id, so after a server **replace** the action must be updated (`aws budgets update-budget-action`).
- ✅ **GitHub OIDC works:** CI `terraform.yml` signs in with no stored keys. Trust policies use GitHub's immutable subject claims (Master Doc D57).
- Supriya's **Fresh Deploy** project is not in this org, so it isn't affected.
