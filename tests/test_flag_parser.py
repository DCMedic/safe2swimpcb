from scripts.update_current_flag import parse_status
def page(flag):return f'<html><body><h3>Current Beach Conditions:</h3><div>{flag}</div><p>Beach conditions are provided by Beach & Surf Patrol</p><h2>Beach Warning Flags</h2><p>Purple Flag</p></body></html>'
def test_yellow():assert parse_status(page('Yellow Flag'))==('Yellow',False,'Yellow')
def test_red():assert parse_status(page('Red Flag'))==('Single Red',False,'Single Red')
def test_double():assert parse_status(page('Double Red Flag'))==('Double Red',False,'Double Red')
def test_green():assert parse_status(page('Green Flag'))==('Green',False,'Green')

def test_purple_overlay():
    html='<h3>Current Beach Conditions:</h3><div>Yellow Flag + Purple Flag</div><p>Beach conditions are provided by Beach & Surf Patrol</p>'
    assert parse_status(html)==('Yellow',True,'Yellow + Purple')


def test_current_page_bare_lowercase_colors_and_dangerous_marine_life():
    html = '''
    <html><body>
      <h3>Current Beach Conditions:</h3>
      <div>yellow and purple</div>
      <div>Dangerous Marine Life</div>
      <p>Beach conditions are provided by Beach & Surf Patrol</p>
      <h2>Beach Warning Flags</h2>
      <p>Red Flag</p>
    </body></html>
    '''
    assert parse_status(html) == ('Yellow', True, 'Yellow + Purple')


def test_current_conditions_can_be_inline_with_heading():
    html = '<h3>Current Beach Conditions: green</h3><p>Beach conditions are provided by Beach & Surf Patrol</p>'
    assert parse_status(html) == ('Green', False, 'Green')
