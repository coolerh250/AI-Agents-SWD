{{/*
Step 51.2C2 batch-job helpers. Shared pieces for the migration Job, backup
CronJob and restore scaffold: restricted SecurityContext, fixed command lookup,
and the bounded /tmp emptyDir. No shell, no automount, no host namespaces.
*/}}

{{- define "aiagents.batch.podSecurityContext" -}}
{{- $g := .Values.global.workloadSecurity -}}
runAsNonRoot: {{ $g.runAsNonRoot }}
runAsUser: {{ $g.runAsUser }}
runAsGroup: {{ $g.runAsGroup }}
seccompProfile:
  type: {{ $g.seccompProfile.type }}
{{- end -}}

{{- define "aiagents.batch.containerSecurityContext" -}}
{{- $g := .Values.global.workloadSecurity -}}
allowPrivilegeEscalation: {{ $g.allowPrivilegeEscalation }}
privileged: {{ $g.privileged }}
readOnlyRootFilesystem: true
capabilities:
  drop:
    {{- range $g.dropCapabilities }}
    - {{ . }}
    {{- end }}
{{- end -}}

{{/* Resolve the FIXED command for a batch job. Call with (dict "root" $ "commandKey" key). */}}
{{- define "aiagents.batch.command" -}}
{{- $c := index .root.Values.batchCommands .commandKey -}}
{{- if $c.shell }}{{ fail (printf "batchCommands.%s.shell must be false" .commandKey) }}{{- end }}
command:
  {{- toYaml $c.command | nindent 2 }}
args:
  {{- toYaml $c.args | nindent 2 }}
{{- end -}}
