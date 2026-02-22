import { useEffect, useState } from "react";
import { subscribeToApiErrors, type ApiErrorEventDetail } from "../observability";

type BannerState = (ApiErrorEventDetail & { visible: boolean }) | null;

export function ApiErrorBanner() {
  const [banner, setBanner] = useState<BannerState>(null);

  useEffect(() => {
    return subscribeToApiErrors((detail) => {
      setBanner({ ...detail, visible: true });
    });
  }, []);

  if (!banner?.visible) {
    return null;
  }

  return (
    <aside className="error app-error-banner" role="alert">
      <strong>Request failed.</strong> {banner.message}
      <button type="button" onClick={() => setBanner(null)}>
        Dismiss
      </button>
    </aside>
  );
}
