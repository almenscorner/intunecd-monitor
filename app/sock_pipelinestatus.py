def pipelinestatus_html(data):
    i = ""
    for item in data:
        if item['result'] == 'failed':
            p = f"""
            <div class="col-xl-3 col-lg-6 col-md-6 col-sm-6 mb-5">
            <div class="card card-stats">
            <div class="card-header p-3 pt-2">
                <div
                    class="icon icon-lg icon-shape bg-gradient-danger shadow-danger text-center border-radius-xl mt-n4 position-absolute">
                    <i class="material-icons opacity-10">error</i>
                </div>
                <div class="text-end pt-1">
                    <span class="text-sm mb-0 text-capitalize text-danger">{item['result']}</span>
                    <h4 class="mb-0">{item['name']}</h4>
                </div>
            </div>
            <hr class="dark horizontal my-0">
            <div class="card-footer d-flex">
                <form method="POST" action="/pipelines/run">
                <div class="row mt-3">
                    <div class="col">
                    <input class="btn btn-sm btn-primary" type="submit" name="{item['id']}" value="Run" />
                    </div>
                </div>
                </form>
                <i class="material-icons position-relative ms-auto text-lg me-1 my-auto">date_range</i>
                <p class="font-weight-normal my-auto">{item['finishTime']}</p>
            </div>
            </div>
            </div> \
            """
            i += p

        elif item['result'] == 'succeeded':
            p = f"""
            <div class="col-xl-3 col-lg-6 col-md-6 col-sm-6 mb-5">
            <div class="card card-stats">
            <div class="card-header p-3 pt-2">
                <div
                    class="icon icon-lg icon-shape bg-gradient-success shadow-success text-center border-radius-xl mt-n4 position-absolute">
                    <i class="material-icons opacity-10">check</i>
                </div>
                <div class="text-end pt-1">
                    <span class="text-sm mb-0 text-capitalize text-success">{item['result']}</span>
                    <h4 class="mb-0">{item['name']}</h4>
                </div>
            </div>
            <hr class="dark horizontal my-0">
            <div class="card-footer d-flex">
                <form method="POST" action="/pipelines/run">
                <div class="row mt-3">
                    <div class="col">
                    <input class="btn btn-sm btn-primary" type="submit" name="{item['id']}" value="Run" />
                    </div>
                </div>
                </form>
                <i class="material-icons position-relative ms-auto text-lg me-1 my-auto">date_range</i>
                <p class="font-weight-normal my-auto">{item['finishTime']}</p>
            </div>
            </div>
            </div> \
            """
            i += p

        elif item['status'] != 'completed':
            p = f"""
            <div class="col-xl-3 col-lg-6 col-md-6 col-sm-6 mb-5">
            <div class="card card-stats">
            <div class="card-header p-3 pt-2">
                <div
                    class="icon icon-lg icon-shape bg-gradient-info shadow-info text-center border-radius-xl mt-n4 position-absolute">
                    <i class="material-icons opacity-10">pending</i>
                </div>
                <div class="text-end pt-1">
                    <span class="text-sm mb-0 text-capitalize text-info">{item['status']}</span>
                    <h4 class="mb-0">{item['name']}</h4>
                </div>
            </div>
            <hr class="dark horizontal my-0">
            <div class="card-footer d-flex">
                <form method="POST" action="/pipelines/run">
                <div class="row mt-3">
                    <div class="col">
                    <div class="spinner-grow spinner-grow-sm text-primary" role="status">
                        <span class="sr-only">Loading...</span>
                    </div>
                    </div>
                </div>
                </form>
                <i class="material-icons position-relative ms-auto text-lg me-1 my-auto">date_range</i>
                <p class="font-weight-normal my-auto">{item['finishTime']}</p>
            </div>
            </div>
            </div> \
            """
            i += p

    html = i

    return html