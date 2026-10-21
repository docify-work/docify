{{- define "data.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: docify
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "data.postgresSelector" -}}
app.kubernetes.io/name: postgres
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/* Env var name holding an env's DB password, e.g. DB_PASSWORD_STAGING */}}
{{- define "data.envPasswordVar" -}}
DB_PASSWORD_{{ upper . }}
{{- end -}}

{{- define "data.backupBucket" -}}
{{- default (printf "docify-backups-%s" (toString .Values.aws.accountId)) .Values.backup.bucket -}}
{{- end -}}

{{/* Validate env names once (they become SQL identifiers and env var names). */}}
{{- define "data.validateEnvs" -}}
{{- range .Values.envs }}
{{- if not (regexMatch "^[a-z0-9_]+$" .) }}
{{- fail (printf "data.envs: %q must match ^[a-z0-9_]+$" .) }}
{{- end }}
{{- end }}
{{- end -}}

{{/* Restricted-style container security context. */}}
{{- define "data.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end -}}
