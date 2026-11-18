---
title: "31. GitLab ID token gate for forge credentials"
status: Active
topics:
  - security
  - gitlab
  - credentials
---

# 31. GitLab ID token gate for forge credentials

Date: 2026-11-18

Related: [fullsend#9597](https://github.com/fullsend-ai/fullsend/issues/9597),
spike [fullsend#9629](https://github.com/fullsend-ai/fullsend/pull/9629),
ADR discussion [fullsend#9631](https://github.com/fullsend-ai/fullsend/pull/9631).

## Hypothesis

Some GitLab adopters cannot set "Minimum role to use pipeline variables"
to `no_one_allowed`. The #9597 spike showed that, without that setting, a
pipeline caller can take the long-lived credentials out of a fullsend job:
a changed `CI_API_V4_URL` sends them to the caller's host, and a file type
`BASH_ENV` variable runs the caller's code before the job script starts.
Nothing inside the job can stop that.

The hypothesis: if the job holds no long-lived credential, and an issuer
outside the job gives one out only after it checks claims that GitLab
signs, then the caller gets nothing, even with full control of pipeline
variables. The claim that matters most is who started the pipeline
(`user_login`), together with `pipeline_source`, `ref_protected`, and
`ci_config_ref_uri`.

## Approach

The issuer is Google Workload Identity Federation (WIF) plus Secret
Manager, so no custom server is needed:

- A WIF pool trusts GitLab.com ID tokens for one project. Its provider
  condition requires the project path, `ref == main`, `ref_protected ==
  true`, the exact `ci_config_ref_uri` of `.gitlab-ci.yml` on `main`,
  `pipeline_source == schedule`, and `user_login` equal to the service
  account.
- A Secret Manager secret holds a **false** forge credential. Only
  identities from that pool can read it.
- A `gate` job requests an ID token (`id_tokens`), exchanges it at Google
  STS, and tries to read the secret. It prints the signed claims and only
  the length and a short SHA-256 prefix of the credential. The STS and
  secret endpoints are literals in the committed files, not CI variables.

Two GitLab.com accounts play the roles:

- **Service account:** a second ordinary account, used only as a bot. It
  owns one inactive schedule. GitLab.com Free cannot create real service
  accounts, so a production install would use a GitLab service account in
  this slot.
- **Person:** the project Owner, who runs every attack.

For the attacks, the project variable role was set to `developer`, the
same setting as the adopter that started #9597. The script puts the
earlier value back when it exits.

## Results

GitLab.com, 2026-11-18, Free tier, SaaS shared runners.

| # | Scenario | Signed claims | Gate result |
|---|---|---|---|
| 1 | Service account runs its own schedule | `user_login`: service account, `pipeline_source: schedule`, `ref_protected: true`, config from `main` | **Credential issued** |
| 2 | Person runs a schedule that the person owns | `user_login`: person, `pipeline_source: schedule` | Refused by STS |
| 3 | Person starts an API pipeline | `pipeline_source: api` | Refused |
| 4 | Person sets `CI_PIPELINE_SOURCE=schedule` as a pipeline variable | Still `pipeline_source: api` | Refused |
| 5 | Person injects a file type `BASH_ENV` (and `ENV`) variable | `pipeline_source: api` | Refused. The injected code ran and could read the ID token, which STS refuses. |
| 6 | Person edits the service account's schedule, or adds a `BASH_ENV` variable to it | none | HTTP 403. Only the owner can change a schedule. |
| 7 | Person retries the service account's scheduled job | `user_login`: person, `pipeline_source: schedule` | Refused |
| 8 | Person takes ownership of the service account's schedule and runs it | `user_login`: person, `pipeline_source: schedule` | Refused |

What the results show:

- **GitLab signs what really happened.** A pipeline variable cannot change
  `pipeline_source` (scenario 4) or the other claims. The gate decides
  outside the job, so code in the job (scenario 5) cannot change the
  decision.
- **`user_login` does the work.** Scenarios 2, 7, and 8 all carry
  `pipeline_source: schedule`. Only the `user_login` check refuses them. A
  retry runs as the person who retried it, and a person who takes
  ownership becomes the pipeline user.
- **A caller cannot get into the service account's pipelines.** The
  person cannot add variables to a schedule they do not own (scenario 6).
  Taking ownership changes `user_login`, so the credential stops (scenario
  8). The worst a Maintainer can do this way is stop the schedule, which
  is visible.
- **Before and after in one run.** In scenario 5, the injected code could
  also read an old long-lived protected variable left from the spike. The
  gated credential was not in reach.

## Not covered

- A real forge credential. The secret here is false. In fullsend the
  issuer would be the mint (ADR 0029), which would hold or issue the role
  and poller credentials after the same claim checks.
- The webhook trigger path. A trigger pipeline runs as the trigger token
  owner. Test it with a trigger token that the service account owns.
- Manual jobs that a person starts with variables inside a service
  account pipeline. A manual job should run as the person, like a retry.
- A Developer as the attacker. The person was the Owner. The gate does not
  read roles, so a Developer should be refused the same way.
- GitLab self-managed versions, which can lack some ID token claims.

## Reproduce

Requirements: `gcloud` with Owner (or the WIF, IAM, and Secret Manager
admin roles) on a GCP project, `glab` signed in as the person, `jq`,
`envsubst`, and two GitLab.com accounts. New GitLab.com accounts must
verify their identity before they can run pipelines.

1. Create a private GitLab.com project. Add the service account user as
   Maintainer.
2. Export the settings. There are no defaults:

   ```bash
   export GCP_PROJECT=<gcp project id>
   export GITLAB_PROJECT=<group/project>
   export SA_LOGIN=<service account username>
   ```

3. Create the GCP parts: `scripts/setup-gcp.sh`
4. Render the CI files into a checkout of the project, then commit and
   push them to `main`: `scripts/render-ci.sh <checkout>`
5. As the person, create an inactive schedule on `main`. As the service
   account, take ownership of it and run it. The job log shows scenario 1.
6. Run the attacks as the person. Set `SA_SCHEDULE_ID` to the schedule ID
   to also run scenarios 6 and 7:

   ```bash
   SA_SCHEDULE_ID=<id> scripts/run-scenarios.sh
   ```

7. For scenarios 2 and 8, create a schedule as the person, or take
   ownership of the service account's schedule, and run it.

Teardown: `scripts/teardown.sh`, then delete the GitLab project.

## Conclusion

The hypothesis holds on GitLab.com. Pipeline variable control, including
code execution through `BASH_ENV`, gives a caller nothing when the job
holds no long-lived credential and the issuer checks the signed
`user_login` and `pipeline_source` claims. This keeps the in project
install and needs no extra GitLab tier. It points the #9597 decision at
mint-issued GitLab credentials, not at a companion project.
