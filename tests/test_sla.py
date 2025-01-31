def test_sla_scenarios():
    """
    Test cases for SLA functionality:
    
    1. New ticket creation
    - Verify SLA deadlines are set based on priority
    - Verify both SLAs start as in_progress
    
    2. First Response
    - Verify adding internal comment marks response SLA as met
    - Verify assigning ticket + changing status marks response SLA as met
    - Verify late response marks SLA as missed
    
    3. Resolution
    - Verify resolving ticket within SLA marks as met
    - Verify resolving ticket after SLA marks as missed
    - Verify reopening ticket resets resolution SLA
    
    4. Priority Changes
    - Verify changing priority recalculates deadlines
    - Verify existing response/resolution status preserved
    
    5. Edge Cases
    - Verify handling of missing SLA configs
    - Verify handling of invalid dates
    - Verify concurrent updates
    """ 