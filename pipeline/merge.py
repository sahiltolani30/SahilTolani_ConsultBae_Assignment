def create_golden_record(cluster: list[dict]) -> dict:
    """
    Takes a cluster of normalized records representing the same person.
    Each record must have a '_source' key ('src1', 'src2', or 'src3').
    Returns ONE golden record with conflict resolution applied.
    """
    golden = {
        'full_name': None,
        'email': None,
        'phone': None,
        'city': None,
        'experience_years': None,
        'ctc_inr': None,
        'hourly_rate_inr': None,
        'skills': '',
        'is_verified': None,
        'projects_completed': None,
        'applied_date': None,
        'gig_status': None,
        'sources': ''
    }
    
    if not cluster:
        return golden

    # Separate by source for priority logic
    src1_recs = [r for r in cluster if r.get('_source') == 'src1']
    src2_recs = [r for r in cluster if r.get('_source') == 'src2']
    src3_recs = [r for r in cluster if r.get('_source') == 'src3']
    
    # 1. Sources tag
    sources_set = set(r.get('_source') for r in cluster if r.get('_source'))
    golden['sources'] = ",".join(sorted(list(sources_set)))
    
    # 2. Name: longest non-abbreviated
    # simple heuristic: longest string by character count
    names = [str(r.get('full_name')).strip() for r in cluster if r.get('full_name')]
    if names:
        golden['full_name'] = max(names, key=len)
        
    # 3. Email: src1 -> src2
    for s_recs in (src1_recs, src2_recs, src3_recs):
        emails = [r.get('email') for r in s_recs if r.get('email')]
        if emails:
            golden['email'] = emails[0]
            break
            
    # 4. Phone: src1 -> src3 -> src2
    for s_recs in (src1_recs, src3_recs, src2_recs):
        phones = [r.get('phone') for r in s_recs if r.get('phone')]
        if phones:
            golden['phone'] = phones[0]
            break
            
    # 5. City: src1 -> src3 -> src2
    for s_recs in (src1_recs, src3_recs, src2_recs):
        cities = [r.get('city') for r in s_recs if r.get('city')]
        if cities:
            golden['city'] = cities[0]
            break
            
    # 6. Experience: max across any source (usually src1)
    exps = [r.get('experience_years') for r in cluster if r.get('experience_years') is not None]
    if exps:
        golden['experience_years'] = max(exps)
        
    # 7. CTC: src1 only
    ctcs = [r.get('ctc_inr') for r in src1_recs if r.get('ctc_inr') is not None]
    if ctcs:
        golden['ctc_inr'] = ctcs[0]
        
    # 8. Hourly Rate: src2 only
    rates = [r.get('hourly_rate_inr') for r in src2_recs if r.get('hourly_rate_inr') is not None]
    if rates:
        golden['hourly_rate_inr'] = rates[0]
        
    # 9. Verified: src3 only
    verified = [r.get('is_verified') for r in src3_recs if r.get('is_verified') is not None]
    if verified:
        golden['is_verified'] = verified[0]
        
    # 10. Projects completed: src3, max
    projs = [r.get('projects_completed') for r in src3_recs if r.get('projects_completed') is not None]
    if projs:
        golden['projects_completed'] = max(projs)
        
    # 11. Applied Date: src1 only
    dates = [r.get('applied_date') for r in src1_recs if r.get('applied_date')]
    if dates:
        golden['applied_date'] = dates[0]
        
    # 12. Gig Status: src2 only
    statuses = [r.get('gig_status') for r in src2_recs if r.get('gig_status')]
    if statuses:
        golden['gig_status'] = statuses[0]
        
    # 13. Skills: UNION of all
    all_skills = []
    for r in cluster:
        skills = r.get('skills', [])
        if isinstance(skills, list):
            all_skills.extend(skills)
        elif isinstance(skills, str) and skills:
            all_skills.append(skills)
            
    # Deduplicate while preserving roughly first seen order
    unique_skills = list(dict.fromkeys(all_skills))
    golden['skills'] = "|".join(unique_skills)
    
    return golden
