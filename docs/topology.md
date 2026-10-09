# Infrastructure topology

Production Health now includes a network map derived from existing health, runtime, and network snapshots. No backend redesign.

## Nodes

Internet → Router → Ubuntu → Docker → Immich  
Router → QNAP → Photo Monitor  
Ubuntu → Telegram

Status is `online` when health is `healthy`, `excellent`, or `good`. Latency is shown when the network snapshot provides it.

## HTTP

`GET /api/v1/system/topology` returns `nodes`, `edges`, and a Mermaid `flowchart LR`.

Dashboard: Production Health → Infrastructure Topology.
