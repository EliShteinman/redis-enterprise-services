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

{{- define "res.registry" -}}
{{- required "image.registry is required: the registry host the images are pulled from" .Values.image.registry }}
{{- end }}

{{- define "res.image" -}}
{{- printf "%s/%s:%s" (include "res.registry" .) .Values.image.repository (.Values.image.tag | default .Chart.AppVersion) }}
{{- end }}

{{- define "res.collectorImage" -}}
{{- printf "%s/%s:%s" (include "res.registry" .) .Values.collector.image.repository .Values.collector.image.tag }}
{{- end }}

{{- define "res.clustersFile" -}}
clusters.yaml
{{- end }}

{{- define "res.mappedFile" -}}
{{- $source := required (printf "files.%s is required: the name of the file in helm/files/ mounted as %s" .name .name) (index .root.Values.files .name) }}
{{- required (printf "files.%s names %s, which is not a file in helm/files/" .name $source) (.root.Files.Get (printf "files/%s" $source)) }}
{{- end }}

{{- define "res.secretValue" -}}
{{- required (printf "secret.%s is required" .name) (index .root.Values.secret .name) }}
{{- end }}
