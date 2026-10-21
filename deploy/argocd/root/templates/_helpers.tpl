{{/*
Common Application pieces.
*/}}

{{/* metadata block for a child Application. Args: dict "ctx" $ "name" "x" "wave" N "finalizer" bool */}}
{{- define "root.appMetadata" -}}
name: {{ .name }}
namespace: argocd
labels:
  app.kubernetes.io/part-of: docify
  app.kubernetes.io/managed-by: argocd-root
annotations:
  # Order of creation inside the root app (lower first). The root waits for
  # each wave to be Healthy before the next (Application health check, V19).
  argocd.argoproj.io/sync-wave: {{ .wave | quote }}
{{- if .finalizer }}
# Deleting the Application (e.g. enabled: false) also deletes its resources.
finalizers:
  - resources-finalizer.argocd.argoproj.io
{{- end }}
{{- end -}}

{{/*
syncPolicy for every child (§13.2): automated + prune + selfHeal, retry with
backoff, create the namespace. Args: dict "ctx" $ "ssa" bool "nsLabels" map
*/}}
{{- define "root.syncPolicy" -}}
syncPolicy:
  automated:
    prune: true
    selfHeal: true
  retry:
    {{- toYaml .ctx.Values.global.retry | nindent 4 }}
  syncOptions:
    - CreateNamespace=true
    # Delete pruned resources last, after new ones are healthy.
    - PruneLast=true
    {{- if .ssa }}
    # Server-side apply: needed for CRDs bigger than the 256 KiB
    # last-applied annotation limit (Prometheus/Argo CD/KEDA CRDs).
    - ServerSideApply=true
    {{- end }}
  {{- with .nsLabels }}
  # Labels/annotations Argo CD puts on the namespace it creates
  # (Pod Security Admission levels, §13.1).
  managedNamespaceMetadata:
    labels:
      {{- toYaml . | nindent 6 }}
  {{- end }}
{{- end -}}

{{/* Relative path from a chart directory back to the repo root, e.g. "deploy/helm/docify" -> "../../../" */}}
{{- define "root.toRepoRoot" -}}
{{- range (splitList "/" (trimSuffix "/" .)) }}../{{ end -}}
{{- end -}}

{{/* PSA label sets (§13.1) */}}
{{- define "root.psa.restricted" -}}
pod-security.kubernetes.io/enforce: restricted
pod-security.kubernetes.io/warn: restricted
{{- end -}}
{{- define "root.psa.baseline" -}}
pod-security.kubernetes.io/enforce: baseline
pod-security.kubernetes.io/warn: restricted
{{- end -}}
{{- define "root.psa.privileged" -}}
pod-security.kubernetes.io/enforce: privileged
pod-security.kubernetes.io/warn: baseline
{{- end -}}
