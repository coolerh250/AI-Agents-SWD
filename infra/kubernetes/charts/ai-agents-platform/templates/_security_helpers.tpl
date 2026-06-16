{{/*
Step 51.2A security helpers. Render the restricted-baseline SecurityContext.

Component `security` blocks may override ONLY runAsUser/runAsGroup/fsGroup,
readOnlyRootFilesystem and writablePaths. runAsNonRoot, seccomp, privilege
escalation, privileged and dropped capabilities come from
global.workloadSecurity and are NOT component-overridable -- there is no
privileged/root/capability-add escape hatch.
*/}}

{{- define "aiagents.podSecurityContext" -}}
{{- $g := .root.Values.global.workloadSecurity -}}
{{- $sec := .comp.security | default dict -}}
runAsNonRoot: {{ $g.runAsNonRoot }}
runAsUser: {{ $sec.runAsUser | default $g.runAsUser }}
runAsGroup: {{ $sec.runAsGroup | default $g.runAsGroup }}
fsGroup: {{ $sec.fsGroup | default $g.fsGroup }}
seccompProfile:
  type: {{ $g.seccompProfile.type }}
{{- end -}}

{{- define "aiagents.containerSecurityContext" -}}
{{- $g := .root.Values.global.workloadSecurity -}}
{{- $sec := .comp.security | default dict -}}
allowPrivilegeEscalation: {{ $g.allowPrivilegeEscalation }}
privileged: {{ $g.privileged }}
readOnlyRootFilesystem: {{ if hasKey $sec "readOnlyRootFilesystem" }}{{ $sec.readOnlyRootFilesystem }}{{ else }}{{ $g.readOnlyRootFilesystem }}{{ end }}
capabilities:
  drop:
    {{- range $g.dropCapabilities }}
    - {{ . }}
    {{- end }}
{{- end -}}
