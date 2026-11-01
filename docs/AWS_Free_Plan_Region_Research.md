# AWS Free Plan: why Sydney, and the options

*Researched 2026-10-27 from AWS's own docs, and checked against live tests with our keys.*

## Verdict

The Sydney lock is **by design, not a bug**. The AWS docs say so in writing, and it matched what our tests showed.

1. **Your home region was decided by your address.** New-experience ("Sign up for AWS (new)") projects get one of three regions, based on the contact-address country. **India → Asia Pacific (Sydney) `ap-southeast-2`.** Mumbai is not an option on this sign-up path.
2. **It can't be changed.** Changing your contact info later doesn't move it, and the docs list "Enable or disable AWS Regions" as **"Not applicable. You cannot modify your AWS Region."** Creating more projects won't help either; every project gets the same region.
3. **AWS enforces it with a fixed SCP (block rule) named `RegionFloor`.** It applies to every project and you can't edit it. That's the "explicit deny in a service control policy" error we got in Mumbai.
4. **Global services still work:** Route 53, CloudFront, IAM, and ACM in us-east-1. So the DNS setup is unaffected.

## The other free-plan block that hits Docify

| Rule (Sid) | What it blocks | Effect on Docify |
|---|---|---|
| `DenyIAMRestrictedActions` → `iam:*Provider*` | Creating identity providers, including **GitHub OIDC** | CI can't use keyless login. It would need an access key stored as a GitHub secret. Confirmed by our test. |
| `DenyIAMRestrictedActions` → `iam:*LoginProfile*` | Console passwords for IAM users | IAM users get CLI keys only. That's fine, it's what we use. |
| `ProtectManagedRoles` | Editing the `role/managed/*` roles AWS creates | None. We create our own roles. |
| `AllowFreeTierServices` | Everything outside an allowlist | Every service Docify uses is **on** the allowlist: EC2, S3, SQS, Lambda, SES, Route 53, CloudFront, ACM, ECR, SSM, EventBridge Scheduler, SNS, Budgets, DLM, KMS, CloudWatch. |

**Not verified:** whether the free plan limits **which EC2 instance types** we can launch. m7i-flex.large is *offered* in Sydney, but we'll only know it's *allowed* when we create the server.

## Ways to get Mumbai

| Option | Mumbai? | Cost / risk | Reversible? |
|---|---|---|---|
| **A. Stay on the Free Plan in Sydney** | ❌ | $0 until the credits run out. About 100–150 ms more API latency from India; the website itself is served by CloudFront near users. | — |
| **B. Upgrade to paid + "Activate advanced features"**, then edit the `RegionFloor` SCP | ✅ | Pay-as-you-go. Remaining credits carry over. **The spend limit is removed** and you're responsible for all costs. You become the AWS Organization admin. | ❌ **Irreversible** (AWS says so) |
| **C. Brand-new account using "Sign up for AWS (advanced)"** with docify.work@gmail.com | ✅ (you pick the region) | Normal account with full control, including OIDC. Free credits for new accounts **should** apply, but check that during sign-up. Needs a new card, phone and verification. | The account can be closed |

Upgrading to the paid plan **alone (without advanced features) is not enough**. `RegionFloor` is part of the policy every project gets on both plans, and AWS says you can only edit it after activating advanced features.

### Option B in detail: switching the current account to Mumbai

You can't move the region with a single setting. It takes three irreversible steps, all done by Supriya:

1. **Upgrade to the Paid plan** (Settings → Billing → Upgrade).
   - It covers *all* projects.
   - Remaining credits carry over.
   - The account no longer closes when the credits run out.
   - On its own, this step **does not unlock regions**. AWS docs: it "does not upgrade you to Sign up for AWS (advanced)". *Irreversible.*
2. **Activate advanced features** (Settings → Projects → Actions → Explore advanced features).
   - Supriya becomes the AWS Organization admin and sets a root password.
   - AWS creates an extra "Identity Delegated Admin" account.
   - **Spend limits are removed**; only budgets and alerts remain.
   - The AWS-managed rules become editable. *Irreversible.*
3. **Edit the `RegionFloor` SCP** (Settings → Projects → Manage policies) to add `ap-south-1`. If AWS hasn't already removed the `iam:*Provider*` deny, remove it too so GitHub OIDC works.
   - After this, the **existing Docify project** can use Mumbai. No new project or keys are needed.

There's no fee for steps 1–3. Usage beyond the remaining credit is billed to the card on file, and there's no hard cap.

## Deadline to remember
Whichever option you pick, Free Plan accounts **expire on whichever comes first: 6 months or when the credits run out.** This account's date is **15 Apr 2027**. After that, AWS suspends the account, keeps the data for 90 days, then **deletes it**. To keep running past that date, you have to upgrade.

## Recommendation
- **For learning now:** Option **A (Sydney)**. It's free and works today. The only real cost is CI using a stored access key instead of OIDC.
- **If the Mumbai + OIDC design (as written in the Master Doc) matters:** Option **C** is cleaner than B. It isn't irreversible and doesn't touch Supriya's existing organization. It's a decision for Ganesh, because it can create a bill.

## Sources
- [AWS Regions for your projects](https://docs.aws.amazon.com/accounts/latest/reference/project-regions.html)
- [Managed policies (SCPs) for projects](https://docs.aws.amazon.com/accounts/latest/reference/scps-and-rcps-for-projects.html)
- [Activate advanced AWS features](https://docs.aws.amazon.com/accounts/latest/reference/activate-advanced-features.html)
- [Compare sign-up options](https://docs.aws.amazon.com/accounts/latest/reference/sign-up-for-aws.html)
- [AWS Free Tier FAQs](https://aws.amazon.com/free/free-tier-faqs/)
