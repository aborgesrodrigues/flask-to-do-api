    CREATE TABLE public."user" (
      username varchar NOT NULL,
      "name" varchar NOT NULL,
      id uuid NOT NULL,
      CONSTRAINT user_pk PRIMARY KEY (id)
    );

    CREATE TABLE public.task (
      description varchar NOT NULL,
      state varchar NOT NULL,
      id uuid NOT NULL,
      user_id uuid NOT NULL
    );


    -- public.task foreign keys

    ALTER TABLE public.task ADD CONSTRAINT task_fk FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE RESTRICT ON UPDATE RESTRICT;