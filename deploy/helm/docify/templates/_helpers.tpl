{{/*
Shared helpers for the docify chart.
Naming is deliberately simple: every env lives in its own namespace
(docify-<env>), so object names don't need a release prefix.
*/}}

{{- define "docify.name" -}}docify{{- end -}}

{{/* Standard Kubernetes labels (https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/) */}}
{{- define "docify.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: docify
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: docify
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Values.image.tag | trunc 63 | quote }}
docify.work/env: {{ .Values.env }}
{{- end -}}

{{/* Selector labels for one component. Usage: include "docify.selectorLabels" (dict "ctx" . "component" "api") */}}
{{- define "docify.selectorLabels" -}}
app.kubernetes.io/name: docify
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* Full label set for one component */}}
{{- define "docify.componentLabels" -}}
{{ include "docify.labels" .ctx }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* Backend image reference. Cloud envs build it from aws.accountId so the account id never sits in Git. */}}
{{- define "docify.image" -}}
{{- if .Values.image.ecrRepository -}}
{{- printf "%s.dkr.ecr.%s.amazonaws.com/%s:%s" (toString .Values.aws.accountId) .Values.aws.region .Values.image.ecrRepository (toString .Values.image.tag) -}}
{{- else -}}
{{- printf "%s:%s" .Values.image.repository (toString .Values.image.tag) -}}
{{- end -}}
{{- end -}}

{{- define "docify.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}{{ .Values.serviceAccount.name }}{{- else -}}default{{- end -}}
{{- end -}}

{{/* Computed names (§8.5, §12.6, §15.2) */}}
{{- define "docify.queueName" -}}docify-{{ .Values.env }}-events{{- end -}}
{{- define "docify.queueURL" -}}
{{- if .Values.config.SQS_QUEUE_URL -}}{{ .Values.config.SQS_QUEUE_URL }}
{{- else -}}https://sqs.{{ .Values.aws.region }}.amazonaws.com/{{ .Values.aws.accountId }}/{{ include "docify.queueName" . }}
{{- end -}}
{{- end -}}
{{- define "docify.dlqURL" -}}
{{- if .Values.config.SQS_DLQ_URL -}}{{ .Values.config.SQS_DLQ_URL }}
{{- else -}}https://sqs.{{ .Values.aws.region }}.amazonaws.com/{{ .Values.aws.accountId }}/{{ include "docify.queueName" . }}-dlq
{{- end -}}
{{- end -}}
{{- define "docify.repoCacheBucket" -}}
{{- if .Values.config.S3_REPO_CACHE_BUCKET -}}{{ .Values.config.S3_REPO_CACHE_BUCKET }}
{{- else -}}docify-repo-cache-{{ .Values.aws.accountId }}
{{- end -}}
{{- end -}}
{{- define "docify.ssmPrefix" -}}
{{- default (printf "/docify/%s" .Values.env) .Values.externalSecrets.ssmPrefix -}}
{{- end -}}
{{- define "docify.dbName" -}}{{ default (printf "docify_%s" .Values.env) .Values.database.name }}{{- end -}}
{{- define "docify.dbUser" -}}{{ default (printf "docify_%s" .Values.env) .Values.database.user }}{{- end -}}

{{/* Pod-level settings shared by every backend pod (api, worker, jobs). */}}
{{- define "docify.podCommon" -}}
serviceAccountName: {{ include "docify.serviceAccountName" . }}
# No pod talks to the Kubernetes API -> don't mount a token (§13.3).
automountServiceAccountToken: false
securityContext:
  {{- toYaml .Values.podSecurityContext | nindent 2 }}
{{- with .Values.imagePullSecrets }}
imagePullSecrets:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}

{{/* Env wiring shared by every backend container: ConfigMap + 2 Secrets. */}}
{{- define "docify.envFrom" -}}
envFrom:
  - configMapRef:
      name: docify-config
  - secretRef:
      name: docify-app
  - secretRef:
      name: docify-db
{{- with .Values.extraEnv }}
env:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}

{{/* readOnlyRootFilesystem needs a writable /tmp (heartbeat file, tempfiles). */}}
{{- define "docify.tmpVolumeMount" -}}
- name: tmp
  mountPath: /tmp
{{- end -}}
{{- define "docify.tmpVolume" -}}
- name: tmp
  emptyDir:
    sizeLimit: 512Mi
{{- end -}}

{{/*
Network-policy role labels. NetworkPolicies select pods by these labels, so a
pod's network access is visible right in its pod template:
  docify.work/net-app: "true"  -> may reach Valkey + Postgres
  docify.work/net-aws: "true"  -> may reach AWS credential endpoint + HTTPS
*/}}
{{- define "docify.netLabels.app" -}}
docify.work/net-app: "true"
{{- end -}}
{{- define "docify.netLabels.aws" -}}
docify.work/net-aws: "true"
{{- end -}}
