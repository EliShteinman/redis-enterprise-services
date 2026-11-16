{{- define "res.fullname" -}}
{{- if contains .Chart.Name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "res.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "res.labels" -}}
{{ include "res.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "res.domain" -}}
{{- required "domain is required: the domain the service runs in (--set domain=<domain> or a values file)" .Values.domain }}
{{- end }}

{{- define "res.routeHost" -}}
{{- .Values.route.host | default (printf "%s.%s" .Values.route.name (include "res.domain" .)) }}
{{- end }}

{{- define "res.image" -}}
{{- printf "%s.%s/%s:%s" .Values.image.registry (include "res.domain" .) .Values.image.repository (.Values.image.tag | default .Chart.AppVersion) }}
{{- end }}

{{- define "res.collectorImage" -}}
{{- printf "%s.%s/%s:%s" .Values.image.registry (include "res.domain" .) .Values.collector.image.repository .Values.collector.image.tag }}
{{- end }}

{{- define "res.clustersFile" -}}
clusters.yaml
{{- end }}
