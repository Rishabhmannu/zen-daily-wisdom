create or replace function update_bandit_on_feedback() returns trigger as $$
declare
  v_arm text;
  v_success boolean;
begin
  select arm_key into v_arm from sent_history where id = new.sent_id;
  if v_arm is null then
    return new;
  end if;

  v_success := coalesce(new.rating, 0) >= 4 and coalesce(new.tone_tag, '') <> 'irrelevant';
  insert into bandit_state (arm_key, alpha, beta, pulls)
    values (
      v_arm,
      1.0 + (case when v_success then 1 else 0 end),
      1.0 + (case when v_success then 0 else 1 end),
      1
    )
  on conflict (arm_key) do update set
    alpha = bandit_state.alpha + (case when v_success then 1 else 0 end),
    beta = bandit_state.beta + (case when v_success then 0 else 1 end),
    pulls = bandit_state.pulls + 1,
    last_updated = now();

  return new;
end;
$$ language plpgsql;

drop trigger if exists on_feedback_update_bandit on feedback;
create trigger on_feedback_update_bandit
after insert on feedback
for each row execute function update_bandit_on_feedback();
