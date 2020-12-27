m = Map("atm_setup", "ATM Setup")
s = m:section(TypedSection, "atm", "Transaction Options")
p = s:option(ListValue, "enabled", "Accept Transaction")
p:value("1", "yes") -- Key and value pairs
p:value("0", "no")
p.default = "yes"
p.rmempty=false
q = s:option(Value, "balance", "balance", "Balance in the bank")
q.default = "10000"
q.optional=false
q.rmempty=false
r = s:option(Value, "fee", "fee", "Transaction fee applied to requests")
r.default = "10"
r.optional=false
r.rmempty=false
t = s:option(Value, "person", "person", "The person in the log files")
t.default = "John Crosant"
t.optional=false
t.rmempty=false

return m

