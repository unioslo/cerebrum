profile = {
    # default sorting 
    'group': {
        'edit': {
            'show_account_create': False,
        },
        'members': {
            'sort': {
                'union': ('+type', '+name'),
                'intersection': ('+type', '+name'),
                'difference': ('+type', '+name'),
            }
        },
        'list': {
            'sort': ('+name',),
            'columns': ('name', 'description'),
        },
        'search': {
            'wildcards': False
        },
        'view': {
            'mode': 'view' # or edit
        },
    },
    'person': {
        'edit': {
            'show_account_create': False,
        },
    },
    'menu': {
    },
    
}

# arch-tag: c819bbd5-247b-43c6-82a8-1e29109264a4
