Alpha experiment scaffolds no longer invent a `PsyNetDev/PsyNet@<local-SHA>` requirement when commit pinning fails; they propagate the origin/push error from `commit_psynet_requirement` instead.
