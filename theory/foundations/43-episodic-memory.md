# 43. Durable typed episodic records

## 43.1 Records and exact recall

An episodic record consists of a contributor-defined type identifier, opaque
immutable payload bytes, producer identity, observation time, optional reported
confidence, parent record references and an optional superseded record reference.
The frame assigns no payload meaning, codec, embedding dimension or memory kind.
Contributors can encode inputs, outputs, outcomes and context in their own types.
Confidence is a recorded assertion, not a calibration certificate.

A record's identity is the digest of its canonical encoding. Appending either
adds a new identity or returns the already identical record. Existing identities
never change. Therefore exact lookup after a fresh insertion returns its value,
and further insertions preserve every previous lookup. These algebraic results
assume collision-free identities and faithful storage; they do not prove a
particular database, hash implementation or crash recovery algorithm.

## 43.2 Provenance and permissions

All parent references must already exist in the same store. Supersession requires
a parent reference of the same type. It adds evidence without deleting the
superseded record or asserting which claim is correct. Producers and observation
times are supplied assertions; append order need not be observation-time order.
No automatic nearest-neighbour search, semantic interpretation or consolidation
strategy belongs in this primitive. Retrieval experts remain replaceable packages
and their wrong answers use ordinary runtime risk accounting.

Store reads and appends are cooperative resource gateways requiring separately
configured effect identifiers. The host provisions and closes the store; experts
receive access only through declared and granted effects. As in §42.4, this does
not contain code that bypasses the gateway and accesses database files directly.

## 43.3 Capacity and lookup scaling

Define a record's charged bytes as its canonical encoding length plus its
reference length. A transaction adds a fresh record only if current charged
bytes plus that charge do not exceed the store's persistent capacity. Duplicate
appends charge nothing. Capacity checks and insertion are one writer transaction,
including across independent handles. No automatic eviction exists: a full store
refuses new records, so it cannot silently remove gate evidence.

This quota bounds logical record bytes, not database pages, indices, journals,
resident memory or filesystem use. Physical capacity enforcement needs a separate
storage boundary. Indexed exact lookup takes logarithmic index work in record
count, plus reading and hashing the chosen record. Large payloads and provenance
lists increase that cost. Append work also depends on the number of parents.
No semantic retrieval or sublinear memory-growth claim follows. Durable typed
records are a prerequisite for the broader continual-learning pipeline, not its
completion.

A bounded append-order reference scan lets external strategies rebuild an index
without retaining all references outside the store. Each fresh append receives
a strictly increasing position in the same transaction; duplicate appends get
no new position. Continuing after the last returned position includes later
committed appends. Scans expose storage order, not observation-time order, and
perform no semantic selection or payload decoding.
