{{/*
Step 51.1 helpers for ai-agents-platform foundation chart.
*/}}

{{- define "aiagents.fullname" -}}
{{- $name := default .Chart.Name .Values.global.nameOverride -}}
{{- printf "%s" $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "aiagents.chartLabel" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Common labels applied to every rendered object. */}}
{{- define "aiagents.commonLabels" -}}
app.kubernetes.io/part-of: ai-agents-platform
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ include "aiagents.chartLabel" . }}
ai-agents-swd/environment: {{ .Values.global.environment | quote }}
ai-agents-swd/step: "51.1"
{{- end -}}

{{/* Per-component labels. Call with (dict "root" $ "name" $name "comp" $comp). */}}
{{- define "aiagents.componentLabels" -}}
{{ include "aiagents.commonLabels" .root }}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/component: {{ .comp.type | default "service" }}
ai-agents-swd/test-only: {{ .comp.testOnly | default false | quote }}
{{- end -}}

{{/* Selector labels (stable subset). Call with (dict "root" $ "name" $name). */}}
{{- define "aiagents.selectorLabels" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/part-of: ai-agents-platform
{{- end -}}

{{/*
Fully-qualified container image reference. Honours an optional global registry
prefix and prefers an immutable digest when one is supplied.
Call with (dict "root" $ "comp" $comp).
*/}}
{{- define "aiagents.image" -}}
{{- $reg := .root.Values.global.imageRegistry | default "" -}}
{{- $repo := .comp.image.repository -}}
{{- $prefix := "" -}}
{{- if $reg }}{{- $prefix = printf "%s/" $reg -}}{{- end -}}
{{- if .comp.image.digest -}}
{{- printf "%s%s@%s" $prefix $repo .comp.image.digest -}}
{{- else -}}
{{- printf "%s%s:%s" $prefix $repo .comp.image.tag -}}
{{- end -}}
{{- end -}}

{{/* ServiceAccount name for a component. Call with (dict "root" $ "name" $name "comp" $comp). */}}
{{- define "aiagents.serviceAccountName" -}}
{{- $sa := .comp.serviceAccount | default dict -}}
{{- if hasKey $sa "name" }}{{ $sa.name }}{{- else -}}{{ printf "%s-%s" (include "aiagents.fullname" .root) .name | trunc 63 | trimSuffix "-" }}{{- end -}}
{{- end -}}
