{{- /*
Shared CronJob template. Used by cronjob-reconcile.yaml and
cronjob-housekeeping.yaml:
  reconcile     every 15 min - reconciler pass (§8.4); needs GitHub + SQS
                -> gets the "aws" network role (IMDS + HTTPS egress).
  housekeeping  03:00 Asia/Kolkata - purge old rows (§6); DB only.
The reconciler is also a singleton via a DB lease row (D32), so
concurrencyPolicy: Forbid is belt-and-braces.
*/ -}}
{{- define "docify.cronjob" -}}
{{- $root := .root }}{{- $name := .name }}{{- $cj := .cj }}
{{- if $cj.enabled }}
apiVersion: batch/v1
kind: CronJob
metadata:
  name: {{ $name }}
  labels:
    {{- include "docify.componentLabels" (dict "ctx" $root "component" $name) | nindent 4 }}
spec:
  schedule: {{ $cj.schedule | quote }}
  timeZone: {{ $root.Values.cronjobs.timeZone }}
  concurrencyPolicy: Forbid
  # The node sleeps most of the day; don't run a backlog of missed runs on
  # wake, only the latest one if it is recent enough.
  startingDeadlineSeconds: {{ $cj.startingDeadlineSeconds }}
  successfulJobsHistoryLimit: 1
  failedJobsHistoryLimit: 2
  jobTemplate:
    spec:
      backoffLimit: 1
      activeDeadlineSeconds: {{ $cj.activeDeadlineSeconds }}
      ttlSecondsAfterFinished: 86400
      template:
        metadata:
          labels:
            {{- include "docify.selectorLabels" (dict "ctx" $root "component" $name) | nindent 12 }}
            {{- include "docify.netLabels.app" $root | nindent 12 }}
            {{- if eq $name "reconcile" }}
            {{- include "docify.netLabels.aws" $root | nindent 12 }}
            {{- end }}
        spec:
          {{- include "docify.podCommon" $root | nindent 10 }}
          restartPolicy: Never
          containers:
            - name: {{ $name }}
              image: {{ include "docify.image" $root }}
              imagePullPolicy: {{ $root.Values.image.pullPolicy }}
              command: {{ toJson $cj.command }}
              {{- include "docify.envFrom" $root | nindent 14 }}
              resources:
                {{- toYaml $root.Values.cronjobs.resources | nindent 16 }}
              securityContext:
                {{- toYaml $root.Values.containerSecurityContext | nindent 16 }}
              volumeMounts:
                {{- include "docify.tmpVolumeMount" $root | nindent 16 }}
          volumes:
            {{- include "docify.tmpVolume" $root | nindent 12 }}
{{- end }}
{{- end -}}
