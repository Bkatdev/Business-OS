"""Offline v16 release checks. No network, provider action, or publishing."""
import os, sqlite3, tempfile
from services.v16_website_engine import reliable_audit_score, _site_spec

def main():
    business={"id":18,"name":"WJ Tree Services & Landscaping","category":"Tree Care","city":"South Plainfield","phone":"(732) 763-3801","website":"https://example.test","rating":4.9,"reviews":132,"emergency_service":1,"address":"South Plainfield, NJ"}
    view={"pages":[{"url":"https://example.test"} for _ in range(5)],"evidence":[
      {"normalized_value":"tree removal tree trimming stump grinding landscaping 24/7 emergency tree service","excerpt":"request a free estimate"}],
      "capabilities":[{"capability_key":"PHONE_CONTACT","observed_state":"PRESENT"},{"capability_key":"ESTIMATE_REQUEST","observed_state":"PRESENT"},{"capability_key":"GENERAL_CONTACT_FORM","observed_state":"PRESENT"}],"assets":[]}
    audit=reliable_audit_score(view,business)
    assert audit["confidence"]=="high"
    spec=_site_spec(view,business,audit)
    assert spec["design"]["family"]=="NATURAL_PREMIUM"
    assert len(spec["services"])>=5
    assert spec["estimate_form"]["tenant_business_id"]==18
    assert "estimate" in spec["sections"] and "services" in spec["sections"]
    # Critical semantic invariant: UNKNOWN never earns a verified capability point.
    a=reliable_audit_score({"pages":view["pages"],"capabilities":[{"capability_key":"ESTIMATE_REQUEST","observed_state":"UNKNOWN"}]},business)
    b=reliable_audit_score({"pages":view["pages"],"capabilities":[{"capability_key":"ESTIMATE_REQUEST","observed_state":"PRESENT"}]},business)
    assert b["score"] > a["score"]
    print("V16 RELEASE CHECKS: PASS")
    print("Natural Premium: PASS")
    print("Tenant-bound estimate spec: PASS")
    print("UNKNOWN-neutral scoring: PASS")
if __name__=='__main__': main()
