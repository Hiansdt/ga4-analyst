import type { DatasetInfo } from '../api/types'

/** The dataset a link asks for (?dataset=thelook), or the first one when it names none or an unknown one. */
export function pickDataset(search: string, available: DatasetInfo[]): string {
  const requested = new URLSearchParams(search).get('dataset')
  return available.find((dataset) => dataset.id === requested)?.id ?? available[0].id
}
