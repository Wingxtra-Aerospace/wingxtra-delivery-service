/**
 * This file is generated from FastAPI OpenAPI schema.
 * Source: ${VITE_API_BASE_URL}/openapi.json
 * Generator: openapi-typescript
 */

export interface components {
  schemas: {
    OrderSummary: {
      id: string;
      public_tracking_id: string;
      merchant_id: string | null;
      customer_name: string | null;
      status: string;
      created_at: string;
      updated_at: string;
    };
    OrdersListResponse: {
      items: components["schemas"]["OrderSummary"][];
      page: number;
      page_size: number;
      total: number;
      pagination: components["schemas"]["PaginationMeta"];
    };
    OrderDetailResponse: components["schemas"]["OrderSummary"];
    EventResponse: {
      id: string;
      order_id: string;
      type: string;
      message: string;
      created_at: string;
    };
    EventsTimelineResponse: {
      items: components["schemas"]["EventResponse"][];
      page: number;
      page_size: number;
      total: number;
      pagination: components["schemas"]["PaginationMeta"];
    };
    PodResponse: {
      order_id: string;
      method?: string | null;
      otp_code?: string | null;
      operator_name?: string | null;
      photo_url?: string | null;
      created_at?: string | null;
    };
    JobResponse: {
      id: string;
      order_id: string;
      assigned_drone_id: string;
      status: string;
      mission_intent_id: string | null;
      eta_seconds?: number | null;
      created_at: string;
      updated_at?: string | null;
    };
    JobsListResponse: {
      items: components["schemas"]["JobResponse"][];
      page: number;
      page_size: number;
      total: number;
      pagination: components["schemas"]["PaginationMeta"];
    };
    TrackingPodSummary: {
      method: string;
      created_at: string;
    };
    TrackingViewResponse: {
      order_id: string;
      public_tracking_id: string;
      status: string;
      milestones?: string[] | null;
      pod_summary?: components["schemas"]["TrackingPodSummary"] | null;
    };
    OrderActionResponse: {
      order_id: string;
      status: string;
    };
    OrderEventIngestResponse: {
      order_id: string;
      status: string;
      applied_events: string[];
    };
    MissionSubmitResponse: {
      order_id: string;
      mission_intent_id: string;
      status: string;
    };
    PaginationMeta: {
      page: number;
      page_size: number;
      total: number;
    };
  };
}

export interface paths {
  "/api/v1/orders": {
    get: {
      parameters: {
        query?: {
          status?: string | null;
          search?: string | null;
          from?: string | null;
          to?: string | null;
          page?: number;
          page_size?: number;
        };
      };
      responses: { 200: { content: { "application/json": components["schemas"]["OrdersListResponse"] } } };
    };
  };
  "/api/v1/orders/{order_id}": {
    get: {
      responses: { 200: { content: { "application/json": components["schemas"]["OrderDetailResponse"] } } };
    };
  };
  "/api/v1/orders/{order_id}/events": {
    get: {
      responses: { 200: { content: { "application/json": components["schemas"]["EventsTimelineResponse"] } } };
    };
    post: {
      responses: { 200: { content: { "application/json": components["schemas"]["OrderEventIngestResponse"] } } };
    };
  };
  "/api/v1/orders/{order_id}/pod": {
    get: {
      responses: { 200: { content: { "application/json": components["schemas"]["PodResponse"] } } };
    };
  };
  "/api/v1/orders/{order_id}/assign": {
    post: {
      responses: { 200: { content: { "application/json": components["schemas"]["OrderActionResponse"] } } };
    };
  };
  "/api/v1/orders/{order_id}/cancel": {
    post: {
      responses: { 200: { content: { "application/json": components["schemas"]["OrderActionResponse"] } } };
    };
  };
  "/api/v1/orders/{order_id}/submit-mission-intent": {
    post: {
      responses: { 200: { content: { "application/json": components["schemas"]["MissionSubmitResponse"] } } };
    };
  };
  "/api/v1/jobs": {
    get: {
      responses: { 200: { content: { "application/json": components["schemas"]["JobsListResponse"] } } };
    };
  };
  "/api/v1/jobs/{job_id}": {
    get: {
      responses: { 200: { content: { "application/json": components["schemas"]["JobResponse"] } } };
    };
  };
  "/api/v1/tracking/{public_tracking_id}": {
    get: {
      responses: { 200: { content: { "application/json": components["schemas"]["TrackingViewResponse"] } } };
    };
  };
}

