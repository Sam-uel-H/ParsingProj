import { apiRequest } from './client'

export interface Domain {
  id: string
  name: string
  description: string | null
  created_by_id: string
  updated_by_id: string
  created_at: string
  updated_at: string
}

export interface DomainCreate {
  name: string
  description?: string | null
}

export function listDomains(signal?: AbortSignal): Promise<Domain[]> {
  return apiRequest<Domain[]>('/domains', { signal })
}

export function createDomain(data: DomainCreate): Promise<Domain> {
  return apiRequest<Domain>('/domains', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function updateDomain(
  domainId: string,
  data: Partial<DomainCreate>,
): Promise<Domain> {
  return apiRequest<Domain>(`/domains/${domainId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}
