const seenCommands=new Set();
async function runGuarded(cmd,paused,fn){
 if(paused)throw Error('Browser bridge paused');
 if(typeof cmd.id!=='string'||!Number.isFinite(cmd.deadline)||cmd.deadline<Date.now())throw Error('Command expired or malformed');
 if(seenCommands.has(cmd.id))throw Error('Duplicate command rejected');
 seenCommands.add(cmd.id);if(seenCommands.size>2000)seenCommands.delete(seenCommands.values().next().value);
 return fn();
}
