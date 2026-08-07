from scripts.update_current_flag import parse_status
def page(flag):return f'<html><body><h3>Current Beach Conditions:</h3><div>{flag}</div><p>Beach conditions are provided by Beach & Surf Patrol</p><h2>Beach Warning Flags</h2><p>Purple Flag</p></body></html>'
def test_yellow():assert parse_status(page('Yellow Flag'))==('Yellow',False,'Yellow')
def test_red():assert parse_status(page('Red Flag'))==('Single Red',False,'Single Red')
def test_double():assert parse_status(page('Double Red Flag'))==('Double Red',False,'Double Red')
def test_green():assert parse_status(page('Green Flag'))==('Green',False,'Green')

def test_purple_overlay():
    html='<h3>Current Beach Conditions:</h3><div>Yellow Flag + Purple Flag</div><p>Beach conditions are provided by Beach & Surf Patrol</p>'
    assert parse_status(html)==('Yellow',True,'Yellow + Purple')
