import { api } from './client'

export interface SchemaField {
  name: string
  type: 'string' | 'integer' | 'number' | 'boolean' | 'date' | 'datetime'
  nullable: boolean
  date_format: string | null
}

export interface InferSchemaResponse {
  fields: SchemaField[]
  detected_format: string
  row_count: number
  label: string | null
}

export const schemaApi = {
  infer: (body: { sample: string; format?: string; label?: string }) =>
    api.post<InferSchemaResponse>('/schema/infer', body),
}
