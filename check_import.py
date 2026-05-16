try:
    from graphene_django.utils import from_global_id
    print("Found in graphene_django.utils")
except ImportError:
    try:
        from graphql_relay import from_global_id
        print("Found in graphql_relay")
    except ImportError:
        try:
            from graphene.relay.node import from_global_id
            print("Found in graphene.relay.node")
        except ImportError:
            print("Not found anywhere common")
