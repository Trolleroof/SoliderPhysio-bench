"""User-authorized removal of the local API dollar cap; retain original charges."""
from decimal import Decimal,ROUND_CEILING
from pathlib import Path
import uuid
from scripts import parallel_compact
from scripts.resume_compact import ProviderAwareLedger
from research_env.core.common import canonical,finite,read,write,file_hash

class UncappedLedger(ProviderAwareLedger):
    def reserve(self,body,pricing):
        prompt=Decimal(str(pricing['prompt']));completion=Decimal(str(pricing['completion']))
        if not all(p.is_finite() and p>=0 for p in (prompt,completion)):raise ValueError('Invalid pricing')
        output=max(body['max_tokens'],450000) if body['model']=='x-ai/grok-4.7' else body['max_tokens']
        amount=int((((len(canonical(body))+4096)*prompt+output*completion)*1000000000).to_integral_value(rounding=ROUND_CEILING))
        identifier=uuid.uuid4().hex
        with self.db:self.db.execute('INSERT INTO charges VALUES (?,?,?,?,?)',(identifier,body['model'],amount,amount,'conservative_reservation'))
        self.output_limits[identifier]=body['max_tokens'];return identifier
    def settle(self,identifier,usage):
        cost=usage.get('cost')
        if finite(cost) and cost>=0:
            amount=int((Decimal(str(cost))*1000000000).to_integral_value(rounding=ROUND_CEILING))
            with self.db:self.db.execute('UPDATE charges SET charged_nano=?, accounting=? WHERE id=?',(amount,'provider_reported',identifier))
        tokens=usage.get('completion_tokens')
        if type(tokens) is int and tokens>self.output_limits.get(identifier,float('inf')):raise ValueError('Provider exceeded requested output budget; return concise tool call')
    def summary(self):
        result=super().summary();result.update(limit_usd=None,remaining_usd=None,local_spend_cap_enforced=False,original_recorded_cap_usd=16)
        return result

def run(key,workers=4):
    root=Path('.leaderboard-runs/compact-eight')
    write(root/'spend-cap-removal.json',{'authorization':'User explicitly requested removal of spending cap and continuation','local_spend_cap_usd':None,'original_ledger_retained':True,'implementation_sha256':file_hash(Path(__file__)),'scope':'Existing 72-episode sweep only; original token and phase limits retained'})
    parallel_compact.ProviderAwareLedger=UncappedLedger
    return parallel_compact.run(key,workers)
