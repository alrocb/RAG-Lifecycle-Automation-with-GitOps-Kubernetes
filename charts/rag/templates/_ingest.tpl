{{/* Pod de ingesta, común al CronJob y al Job inicial. Recibe la lista de argumentos extra. */}}
{{- define "rag.ingestPod" -}}
restartPolicy: Never
containers:
  - name: ingest
    image: "{{ .root.Values.images.app }}:{{ .root.Values.images.tag }}"
    command: ["python", "-m", "rag.ingest", "--data-dir", "/data"{{ range .args }}, {{ . | quote }}{{ end }}]
    env:
      - name: QDRANT_URL
        value: http://rag-qdrant:6333
      # Los materiales se descargan con el rol de la máquina (IMDSv2): no hay credenciales.
      - name: MATERIALS_BUCKET
        value: {{ .root.Values.ingest.bucket | quote }}
      - name: AWS_REGION
        value: {{ .root.Values.ingest.region | quote }}
    volumeMounts:
      - name: data
        mountPath: /data
    resources:
      {{- toYaml .root.Values.ingest.resources | nindent 6 }}
volumes:
  - name: data
    emptyDir:
      sizeLimit: 2Gi
{{- end }}
