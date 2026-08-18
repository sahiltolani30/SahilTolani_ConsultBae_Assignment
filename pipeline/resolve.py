class UnionFind:
    """Disjoint set data structure for transitive entity clustering."""
    def __init__(self, size):
        self.parent = list(range(size))
        self.rank = [0] * size
        
    def find(self, i):
        # Path compression
        if self.parent[i] == i:
            return i
        self.parent[i] = self.find(self.parent[i])
        return self.parent[i]
        
    def union(self, i, j):
        # Union by rank
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i != root_j:
            if self.rank[root_i] < self.rank[root_j]:
                self.parent[root_i] = root_j
            elif self.rank[root_i] > self.rank[root_j]:
                self.parent[root_j] = root_i
            else:
                self.parent[root_j] = root_i
                self.rank[root_i] += 1

def resolve_entities(records: list[dict]) -> list[list[dict]]:
    """
    Takes all normalized records from all sources.
    Returns clusters of records representing the same person.
    Matches are based on identical email OR identical phone.
    """
    if not records:
        return []
        
    uf = UnionFind(len(records))
    
    email_to_idx = {}
    phone_to_idx = {}
    
    for idx, rec in enumerate(records):
        email = rec.get('email')
        phone = rec.get('phone')
        
        # If we see an email we've seen before, this record belongs to the same person
        if email:
            if email in email_to_idx:
                uf.union(idx, email_to_idx[email])
            else:
                email_to_idx[email] = idx
                
        # If we see a phone we've seen before, this record belongs to the same person
        if phone:
            if phone in phone_to_idx:
                uf.union(idx, phone_to_idx[phone])
            else:
                phone_to_idx[phone] = idx
                
    # Group records by their connected component root
    from collections import defaultdict
    clusters = defaultdict(list)
    
    for idx in range(len(records)):
        root = uf.find(idx)
        clusters[root].append(records[idx])
        
    return list(clusters.values())
